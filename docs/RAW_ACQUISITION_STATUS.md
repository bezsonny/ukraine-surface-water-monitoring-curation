# Raw-source acquisition status

## Completed in this package

- 77 source groups registered.
- exact rolling-resource revision URLs retained where available;
- historical standalone resource IDs retained;
- three independently verified raw SHA-256 values from the prior Q2–Q4 2020 audit are embedded as cross-checks;
- full expected curated-content fingerprints computed for all 77 source groups;
- raw parser, structural repair, date-autoconversion recovery, QC and validation pipeline implemented;
- unit tests implemented and executed.

## Not yet byte-archived in this conversation runtime

The complete 77-file raw byte archive has not been persisted in this environment. The official portal files can be read through the web interface, but the execution environment does not provide a reliable direct file-download channel for preserving all remote byte streams.

For that reason the package contains a standard-library fetcher and GitHub Actions workflow. Running `python run_pipeline.py` on a normal internet-connected machine or triggering the workflow will create the raw archive, independent SHA-256 checksums and the full rebuild.

This limitation is explicitly recorded rather than filling `Independent_Raw_SHA256` values without the actual bytes.
