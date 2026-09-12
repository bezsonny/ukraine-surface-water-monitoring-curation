#!/usr/bin/env python3
"""Run raw acquisition -> curation -> QC -> publication assembly -> validation."""
import argparse,subprocess,sys

def call(cmd):
    print("+"," ".join(map(str,cmd)),flush=True)
    subprocess.run(cmd,check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--skip-fetch",action="store_true",help="Use pre-populated raw/ directory.")
    args=ap.parse_args()
    py=sys.executable
    if not args.skip_fetch:
        call([py,"scripts/fetch_raw_sources.py"])
    call([py,"scripts/curate_raw.py"])
    call([py,"scripts/domain_qc.py"])
    call([
        py,"scripts/assemble_publication.py",
        "--zero-review","work/zero_semantics_review_from_raw.csv"
    ])
    call([py,"scripts/validate_against_reference.py"])
    print("PIPELINE PASSED")

if __name__=="__main__":
    main()
