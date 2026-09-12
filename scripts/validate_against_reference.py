#!/usr/bin/env python3
"""Validate a raw-origin rebuild against frozen curated and publication-level reference fingerprints."""
import argparse,csv,hashlib,sys
from collections import defaultdict
from pathlib import Path
from common import load_schema, canonical_content_hash

def read(path):
    with open(path,encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f)
        return r.fieldnames,list(r)

def publication_hash(records, fields):
    lines=[]
    for r in sorted(records,key=lambda x:x["Record_ID"]):
        lines.append("\x1f".join(r.get(k,"") for k in fields))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--schema",default="config/schema.csv")
    ap.add_argument("--registry",default="config/source_registry.csv")
    ap.add_argument("--input",default="work/curated_from_raw.csv")
    ap.add_argument("--publication",default="work/observations_from_raw.csv")
    ap.add_argument("--flags",default="work/quality_flags_from_raw.csv")
    ap.add_argument("--corrections",default="work/technical_corrections_from_raw.csv")
    ap.add_argument("--zero-review",default="work/zero_semantics_review_from_raw.csv")
    ap.add_argument("--publication-fields",default="reference/publication_observation_fields.txt")
    ap.add_argument("--publication-hash",default="reference/expected_publication_observations_sha256.txt")
    args=ap.parse_args()

    fields=[x["name"] for x in load_schema(Path(args.schema))]
    _,reg_rows=read(args.registry)
    reg={x["Source_ID"]:x for x in reg_rows}
    _,rows=read(args.input)

    by=defaultdict(list)
    for r in rows:by[r["Source_ID"]].append(r)

    errors=[]
    for sid,src in reg.items():
        got=canonical_content_hash(by[sid],fields)
        if got!=src["Expected_Curated_Content_SHA256"]:
            errors.append(f"{sid}: curated fingerprint mismatch")
        if len(by[sid])!=int(src["Expected_Record_Count"]):
            errors.append(f"{sid}: row count mismatch {len(by[sid])} != {src['Expected_Record_Count']}")

    if len(rows)!=59670: errors.append(f"overall curated row count {len(rows)} != 59670")
    ids=[x["Record_ID"] for x in rows]
    if len(ids)!=len(set(ids)): errors.append("Record_ID not unique")

    pub_fields,pub=read(args.publication)
    expected_fields=Path(args.publication_fields).read_text(encoding="utf-8").splitlines()
    if pub_fields!=expected_fields:
        errors.append("publication observation header/order mismatch")
    expected_hash=Path(args.publication_hash).read_text(encoding="utf-8").strip()
    got_hash=publication_hash(pub,expected_fields)
    if got_hash!=expected_hash:
        errors.append(f"publication content hash mismatch {got_hash} != {expected_hash}")

    _,flags=read(args.flags)
    _,corr=read(args.corrections)
    _,zero=read(args.zero_review)
    if len(flags)!=1585: errors.append(f"quality flag count {len(flags)} != 1585")
    if len(corr)!=1608: errors.append(f"technical correction count {len(corr)} != 1608")
    if len(zero)!=1974: errors.append(f"zero-review count {len(zero)} != 1974")

    if errors:
        print("VALIDATION FAILED")
        for e in errors: print(" -",e)
        sys.exit(1)

    print("VALIDATION PASSED")
    print(f"sources={len(reg)} curated_records={len(rows)} publication_records={len(pub)}")
    print(f"quality_flags={len(flags)} technical_corrections={len(corr)} zero_review={len(zero)}")
    print(f"publication_sha256={got_hash}")

if __name__=="__main__":
    main()
