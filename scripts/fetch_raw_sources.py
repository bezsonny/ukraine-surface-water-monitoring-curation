#!/usr/bin/env python3
"""Acquire immutable raw CSV byte streams from data.gov.ua and record SHA-256 hashes."""
from __future__ import annotations
import argparse, csv, json, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
from common import sha256_file

API_BASE="https://data.gov.ua/api/3/action"
UA="surface-water-dataset-reproducibility/1.1 (+research-data-curation)"

def load_registry(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))

def download(url,path):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=180) as r, path.open("wb") as f:
        while True:
            chunk=r.read(1024*1024)
            if not chunk: break
            f.write(chunk)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",default="config/source_registry.csv")
    ap.add_argument("--raw-dir",default="raw")
    ap.add_argument("--metadata-dir",default="raw_metadata")
    ap.add_argument("--manifest-out",default="raw_archive_manifest.csv")
    ap.add_argument("--sleep",type=float,default=0.25)
    args=ap.parse_args()

    raw=Path(args.raw_dir); meta=Path(args.metadata_dir)
    raw.mkdir(parents=True,exist_ok=True); meta.mkdir(parents=True,exist_ok=True)
    registry=load_registry(Path(args.registry))
    manifest=[]

    for src in registry:
        sid=src["Source_ID"]
        strategy=src["Acquisition_Strategy"]
        urls=[]
        api_json=None
        if strategy=="ckan_resource_show":
            api_url=f"{API_BASE}/resource_show?id={src['Resource_ID']}"
            api_json=get_json(api_url)
            if not api_json.get("success"):
                raise RuntimeError(f"resource_show failed for {sid}")
            (meta/f"{sid}_resource_show.json").write_text(
                json.dumps(api_json,ensure_ascii=False,indent=2),encoding="utf-8")
            urls=[api_json["result"]["url"]]
        elif strategy=="direct_revision_url":
            urls=[src["Revision_Download_URLs"]]
        elif strategy=="candidate_revision_urls":
            urls=[x.strip() for x in src["Revision_Download_URLs"].split("|") if x.strip()]
        else:
            raise ValueError(strategy)

        for i,url in enumerate(urls,1):
            suffix="" if len(urls)==1 else f"_candidate{i}"
            path=raw/f"{sid}{suffix}.csv"
            download(url,path)
            digest=sha256_file(path)
            manifest.append({
                "Source_ID":sid,"Source_Sheet":src["Source_Sheet"],
                "Candidate_Index":i if len(urls)>1 else "",
                "Downloaded_File":path.as_posix(),
                "Download_URL":url,
                "Retrieved_UTC":datetime.now(timezone.utc).isoformat(),
                "SHA256":digest,
                "Size_Bytes":path.stat().st_size,
                "Known_Independent_Raw_SHA256":src["Known_Independent_Raw_SHA256"],
                "Known_SHA256_Match":(
                    "true" if src["Known_Independent_Raw_SHA256"] and digest==src["Known_Independent_Raw_SHA256"]
                    else "false" if src["Known_Independent_Raw_SHA256"] else ""
                )
            })
            time.sleep(args.sleep)

    with open(args.manifest_out,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(manifest[0].keys()))
        w.writeheader(); w.writerows(manifest)
    print(f"Downloaded {len(manifest)} raw file(s) for {len(registry)} source groups.")

if __name__=="__main__":
    main()
