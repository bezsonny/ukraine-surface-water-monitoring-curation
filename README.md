# Raw-to-publication reproducibility pipeline v1.1

This package is the next reproducibility layer for the dataset
**“Harmonized surface-water monitoring data for Ukraine, 2003–July 2026.”**

It is designed to rebuild the curated dataset from the **original State Agency of Water Resources of Ukraine CSV resources**, rather than from the intermediate Excel master.


## Associated dataset

Reserved Zenodo dataset DOI: **10.5281/zenodo.22722596** (https://doi.org/10.5281/zenodo.22722596). The dataset record should be made public before the manuscript is submitted.

## What is included

- `config/source_registry.csv` — all 77 source groups with official resource/revision identifiers, acquisition strategy, expected row counts and curated-content SHA-256 fingerprints.
- `scripts/fetch_raw_sources.py` — downloads exact revision URLs where available; otherwise resolves the current historical resource URL through the official CKAN `resource_show` API; calculates SHA-256 for every acquired byte stream.
- `scripts/curate_raw.py` — parses semicolon-delimited UTF-8 CSV, repairs structural semicolons inside `Post_Name`, converts `NULL` to machine-readable missing values, trims outer whitespace, and deterministically repairs spreadsheet date auto-conversion artefacts.
- `scripts/domain_qc.py` — regenerates domain QC flags.
- `scripts/assemble_publication.py` — attaches row-level QC/correction indicators.
- `scripts/validate_against_reference.py` — checks every source group against the frozen v1.0 expected content fingerprint.
- `run_pipeline.py` — orchestrates the complete workflow.
- `tests/` — unit tests for known structural and date-conversion failure modes.
- `.github/workflows/rebuild.yml` — manual GitHub Actions workflow for a cloud rebuild.

## Important design choice

The pipeline does not silently "correct" environmental extremes. It corrects only deterministic technical conversion artefacts. Source-published domain anomalies are retained and flagged.

## Raw acquisition

Run:

```bash
python run_pipeline.py
```

This will:
1. retrieve the official source CSV files;
2. save raw byte streams under `raw/`;
3. record download URLs, UTC retrieval time, file size and independent SHA-256 in `raw_archive_manifest.csv`;
4. curate all source periods;
5. recompute QC;
6. validate all 77 source groups against the frozen reference fingerprints.

If raw files have already been archived:

```bash
python run_pipeline.py --skip-fetch
```

## Expected validation target

- source groups: **77**
- curated records: **59,670**
- unique `Record_ID`: **59,670**
- deterministic technical corrections: **1,608**
- source content is checked per source group against `Expected_Curated_Content_SHA256`.

## May 2024

The official portal exposes two candidate revisions for the May 2024 source group. The fetcher downloads both. `curate_raw.py` compares the complete normalized content of each candidate with the frozen expected fingerprint:
- one match → uniquely resolved;
- multiple matches → byte streams differ or duplicate revisions may exist, but the curated normalized content is equivalent;
- no match → pipeline fails rather than guessing.

## Requirements

Python 3.10+; standard library only.
