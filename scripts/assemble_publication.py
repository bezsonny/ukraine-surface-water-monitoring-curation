#!/usr/bin/env python3
"""Assemble final observations.csv from curated-from-raw plus recomputed QC/correction tables."""
import argparse,csv
from collections import defaultdict,Counter

def read(path):
    with open(path,encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f);return r.fieldnames,list(r)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--curated",default="work/curated_from_raw.csv")
    ap.add_argument("--flags",default="work/quality_flags_from_raw.csv")
    ap.add_argument("--corrections",default="work/technical_corrections_from_raw.csv")
    ap.add_argument("--zero-review",default="")
    ap.add_argument("--output",default="work/observations_from_raw.csv")
    args=ap.parse_args()
    fields,obs=read(args.curated);_,flags=read(args.flags);_,corr=read(args.corrections)
    fb=defaultdict(list)
    for x in flags:fb[x["Record_ID"]].append(x)
    cb=defaultdict(list)
    for x in corr:cb[x["Record_ID"]].append(x)
    zc=Counter()
    if args.zero_review:
        _,zr=read(args.zero_review)
        zc=Counter(x["Record_ID"] for x in zr)
    out_fields=fields+["QC_Flag_Count","QC_Codes","QC_High_Priority","Technical_Correction_Count","Technical_Correction_Codes","Zero_Semantics_Review_Count"]
    with open(args.output,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=out_fields);w.writeheader()
        for r in obs:
            fs=fb[r["Record_ID"]];cs=cb[r["Record_ID"]]
            o=dict(r)
            o["QC_Flag_Count"]=len(fs)
            o["QC_Codes"]="|".join(sorted({x["Flag_Code"] for x in fs}))
            o["QC_High_Priority"]="true" if any(x["Severity"]=="high" for x in fs) else "false"
            o["Technical_Correction_Count"]=len(cs)
            o["Technical_Correction_Codes"]="|".join(sorted({x["Correction_Code"] for x in cs}))
            o["Zero_Semantics_Review_Count"]=zc[r["Record_ID"]]
            w.writerow(o)
    print(f"Assembled {len(obs)} records.")

if __name__=="__main__":
    main()
