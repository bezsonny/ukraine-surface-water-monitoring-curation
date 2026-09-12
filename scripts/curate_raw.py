#!/usr/bin/env python3
"""Parse, structurally repair and deterministically curate raw State Water Agency CSV resources."""
from __future__ import annotations
import argparse, csv
from pathlib import Path
from common import load_schema, parse_raw_csv, curate_record, canonical_content_hash

def read_registry(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def write(path,rows,fields):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--schema",default="config/schema.csv")
    ap.add_argument("--registry",default="config/source_registry.csv")
    ap.add_argument("--raw-dir",default="raw")
    ap.add_argument("--outdir",default="work")
    args=ap.parse_args()

    schema=load_schema(Path(args.schema))
    fields=[x["name"] for x in schema]
    registry=read_registry(Path(args.registry))
    rawdir=Path(args.raw_dir); out=Path(args.outdir); out.mkdir(parents=True,exist_ok=True)

    all_records=[]; all_corr=[]; all_struct=[]; source_report=[]

    for src in registry:
        sid=src["Source_ID"]
        candidates=sorted(rawdir.glob(f"{sid}*.csv"))
        if not candidates:
            raise FileNotFoundError(f"No raw file for {sid}")
        parsed_candidates=[]
        for path in candidates:
            raw_rows,struct=parse_raw_csv(path,sid,src["Source_Sheet"],fields)
            curated=[]; corr=[]
            for rr in raw_rows:
                cr,cc=curate_record(rr,fields)
                curated.append(cr)
                for c in cc:
                    c.update({
                        "Record_ID":cr["Record_ID"],"Post_ID":cr["Post_ID"],
                        "Controle_Date":cr["Controle_Date"],"Source_ID":sid,
                        "Source_Sheet":src["Source_Sheet"],"Source_Line":rr["_source_line"]
                    })
                    corr.append(c)
            h=canonical_content_hash(curated,fields)
            parsed_candidates.append((path,curated,corr,struct,h))

        matches=[x for x in parsed_candidates if x[4]==src["Expected_Curated_Content_SHA256"]]
        if len(matches)==1:
            chosen=matches[0]; status="unique_fingerprint_match"
        elif len(matches)>1:
            # Content-equivalent portal revisions: retain first deterministically,
            # archive byte hashes separately; normalized dataset identity is the same.
            chosen=matches[0]; status="multiple_content_equivalent_matches"
        else:
            details="; ".join(f"{x[0].name}:{x[4]}" for x in parsed_candidates)
            raise RuntimeError(f"{sid}: no candidate matches expected fingerprint. {details}")

        path,curated,corr,struct,h=chosen
        all_records.extend(curated); all_corr.extend(corr)
        for s in struct:
            s["Raw_File"]=path.name
            all_struct.append(s)
        source_report.append({
            "Source_ID":sid,"Chosen_Raw_File":path.name,
            "Record_Count":len(curated),
            "Curated_Content_SHA256":h,
            "Expected_Curated_Content_SHA256":src["Expected_Curated_Content_SHA256"],
            "Fingerprint_Match":"true",
            "Selection_Status":status,
            "Candidate_Count":len(parsed_candidates),
        })

    # Natural key and Record_ID validation.
    ids=[r["Record_ID"] for r in all_records]
    keys=[(r["Post_ID"],r["Controle_Date"]) for r in all_records]
    if len(ids)!=len(set(ids)): raise RuntimeError("Duplicate Record_ID")
    if len(keys)!=len(set(keys)): raise RuntimeError("Duplicate Post_ID + Controle_Date")

    record_fields=fields+["Source_ID","Source_Sheet","Record_ID"]
    write(out/"curated_from_raw.csv",all_records,record_fields)
    corr_fields=["Record_ID","Post_ID","Controle_Date","Field","Correction_Code","Original_Value","Corrected_Value","Correction_Rule","Source_ID","Source_Sheet","Source_Line"]
    write(out/"technical_corrections_from_raw.csv",all_corr,corr_fields)
    struct_fields=["Source_ID","Source_Sheet","Source_Line","raw_field_count","post_id","name_fragments","repaired_post_name","Raw_File"]
    write(out/"structural_repairs_from_raw.csv",all_struct,struct_fields)
    write(out/"source_fingerprint_validation.csv",source_report,list(source_report[0].keys()))
    print(f"Curated {len(all_records)} records; corrections={len(all_corr)}; structural_repairs={len(all_struct)}.")

if __name__=="__main__":
    main()
