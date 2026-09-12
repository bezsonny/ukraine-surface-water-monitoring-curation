#!/usr/bin/env python3
"""Acquire immutable raw CSV byte streams from data.gov.ua and record SHA-256 hashes.

This version is deliberately conservative about request rate:
- honors HTTP Retry-After where supplied;
- retries HTTP 429 and transient 5xx errors with exponential backoff;
- retries network timeouts / connection resets;
- throttles successful requests;
- writes to a temporary .part file and atomically renames only after a complete download.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from common import sha256_file

API_BASE = "https://data.gov.ua/api/3/action"
UA = (
    "surface-water-dataset-reproducibility/1.2.2 "
    "(research data curation; contact: vitalii.bezsonnyi@hneu.net)"
)

RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}


def load_registry(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _retry_delay(exc, attempt: int, base_delay: float, max_delay: float) -> float:
    """Return wait time in seconds, honoring Retry-After where possible."""
    retry_after = None
    if isinstance(exc, urllib.error.HTTPError):
        retry_after = exc.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), max_delay)
        except ValueError:
            # HTTP-date form is uncommon here; fall back to exponential backoff.
            pass

    # Exponential backoff with small jitter.
    delay = min(base_delay * (2 ** max(attempt - 1, 0)), max_delay)
    return delay + random.uniform(0.0, min(1.0, delay * 0.1))


def _open_with_retry(
    url: str,
    *,
    timeout: int,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
):
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "*/*",
                "Connection": "close",
            },
        )
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in RETRYABLE_HTTP or attempt == max_attempts:
                raise
            wait = _retry_delay(exc, attempt, base_delay, max_delay)
            print(
                f"HTTP {exc.code} for {url} "
                f"(attempt {attempt}/{max_attempts}); retrying in {wait:.1f}s",
                flush=True,
            )
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_exc = exc
            if attempt == max_attempts:
                raise
            wait = _retry_delay(exc, attempt, base_delay, max_delay)
            print(
                f"Network error for {url}: {exc!r} "
                f"(attempt {attempt}/{max_attempts}); retrying in {wait:.1f}s",
                flush=True,
            )
            time.sleep(wait)

    if last_exc:
        raise last_exc
    raise RuntimeError(f"Unable to open URL: {url}")


def get_json(
    url: str,
    *,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
):
    with _open_with_retry(
        url,
        timeout=120,
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
    ) as r:
        return json.loads(r.read().decode("utf-8"))


def download(
    url: str,
    path: Path,
    *,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
):
    tmp = path.with_suffix(path.suffix + ".part")
    if tmp.exists():
        tmp.unlink()

    try:
        with _open_with_retry(
            url,
            timeout=180,
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
        ) as r, tmp.open("wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="config/source_registry.csv")
    ap.add_argument("--raw-dir", default="raw")
    ap.add_argument("--metadata-dir", default="raw_metadata")
    ap.add_argument("--manifest-out", default="raw_archive_manifest.csv")
    ap.add_argument(
        "--sleep",
        type=float,
        default=1.5,
        help="Throttle delay after each successful remote request/download (seconds).",
    )
    ap.add_argument(
        "--max-attempts",
        type=int,
        default=8,
        help="Maximum attempts for retryable HTTP/network failures.",
    )
    ap.add_argument(
        "--base-delay",
        type=float,
        default=5.0,
        help="Initial exponential-backoff delay after a retryable failure.",
    )
    ap.add_argument(
        "--max-delay",
        type=float,
        default=90.0,
        help="Maximum backoff delay in seconds.",
    )
    args = ap.parse_args()

    raw = Path(args.raw_dir)
    meta = Path(args.metadata_dir)
    raw.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)

    registry = load_registry(Path(args.registry))
    manifest = []

    remote_request_count = 0

    for source_index, src in enumerate(registry, start=1):
        sid = src["Source_ID"]
        strategy = src["Acquisition_Strategy"]
        urls = []

        print(
            f"[{source_index}/{len(registry)}] Preparing {sid} "
            f"({src['Source_Sheet']})",
            flush=True,
        )

        if strategy == "ckan_resource_show":
            api_url = f"{API_BASE}/resource_show?id={src['Resource_ID']}"
            api_json = get_json(
                api_url,
                max_attempts=args.max_attempts,
                base_delay=args.base_delay,
                max_delay=args.max_delay,
            )
            remote_request_count += 1
            if not api_json.get("success"):
                raise RuntimeError(f"resource_show failed for {sid}")
            (meta / f"{sid}_resource_show.json").write_text(
                json.dumps(api_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            urls = [api_json["result"]["url"]]
            time.sleep(args.sleep)

        elif strategy == "direct_revision_url":
            urls = [src["Revision_Download_URLs"]]

        elif strategy == "candidate_revision_urls":
            urls = [
                x.strip()
                for x in src["Revision_Download_URLs"].split("|")
                if x.strip()
            ]

        else:
            raise ValueError(f"Unsupported acquisition strategy: {strategy}")

        for i, url in enumerate(urls, start=1):
            suffix = "" if len(urls) == 1 else f"_candidate{i}"
            path = raw / f"{sid}{suffix}.csv"

            print(
                f"  downloading candidate {i}/{len(urls)} -> {path.name}",
                flush=True,
            )

            download(
                url,
                path,
                max_attempts=args.max_attempts,
                base_delay=args.base_delay,
                max_delay=args.max_delay,
            )
            remote_request_count += 1

            digest = sha256_file(path)
            known = src["Known_Independent_Raw_SHA256"]

            manifest.append(
                {
                    "Source_ID": sid,
                    "Source_Sheet": src["Source_Sheet"],
                    "Candidate_Index": i if len(urls) > 1 else "",
                    "Downloaded_File": path.as_posix(),
                    "Download_URL": url,
                    "Retrieved_UTC": datetime.now(timezone.utc).isoformat(),
                    "SHA256": digest,
                    "Size_Bytes": path.stat().st_size,
                    "Known_Independent_Raw_SHA256": known,
                    "Known_SHA256_Match": (
                        "true"
                        if known and digest == known
                        else "false"
                        if known
                        else ""
                    ),
                }
            )
            time.sleep(args.sleep)

    if not manifest:
        raise RuntimeError("No raw source files were downloaded.")

    with open(args.manifest_out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)

    print(
        f"Downloaded {len(manifest)} raw file(s) for {len(registry)} source groups "
        f"using {remote_request_count} remote request(s).",
        flush=True,
    )


if __name__ == "__main__":
    main()
