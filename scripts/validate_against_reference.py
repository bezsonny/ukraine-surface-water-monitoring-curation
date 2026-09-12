#!/usr/bin/env python3
"""Validate a raw-origin rebuild against the frozen publication-candidate reference fingerprints."""
import argparse,csv,hashlib,sys
from collections import defaultdict
from pathlib import Path
from common import load_schema, canonical_content_hash

def read(path):
    with open(path,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--schema",default="config/schema.csv")
    ap.add_argument("--registry",default="config/source_registry.csv")
    ap.add_argument("--input",default="work/curated_from_raw.csv")
    args=ap.parse_args()
    fields=[x["name"] for x in load_schema(Path(args.schema))]
    reg={x["Source_ID"]:x for x in read(args.registry)}
    rows=read(args.input)
    by=defaultdict(list)
    for r in rows:by[r["Source_ID"]].append(r)
    errors=[]
    for sid,src in reg.items():
        got=canonical_content_hash(by[sid],fields)
        if got!=src["Expected_Curated_Content_SHA256"]:
            errors.append(f"{sid}: fingerprint mismatch")
        if len(by[sid])!=int(src["Expected_Record_Count"]):
            errors.append(f"{sid}: row count mismatch {len(by[sid])} != {src['Expected_Record_Count']}")
    if len(rows)!=59670:errors.append(f"overall row count {len(rows)} != 59670")
    ids=[x["Record_ID"] for x in rows]
    if len(ids)!=len(set(ids)):errors.append("Record_ID not unique")
    if errors:
        print("VALIDATION FAILED");[print(" -",e) for e in errors];sys.exit(1)
    print("VALIDATION PASSED")
    print(f"sources={len(reg)} records={len(rows)} unique_record_ids={len(set(ids))}")

if __name__=="__main__":
    main()
