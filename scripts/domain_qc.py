#!/usr/bin/env python3
"""Recompute domain-level QC flags and zero-semantics review from curated-from-raw observations."""
from __future__ import annotations
import argparse,csv,math
from collections import defaultdict
from datetime import datetime

MEAS=["Azot","BSK5","Zavisli","Kisen","Sulfat","Hlorid","Amoniy","Nitrat","Nitrit","Fosfat","SPAR","Permanganat","HSK","Fitoplan","Atrazin","Simazin"]

def num(x):
    try: return float(x) if x not in ("",None) else None
    except: return None

def quantile(xs,q):
    xs=sorted(xs)
    if not xs:return None
    if len(xs)==1:return xs[0]
    p=(len(xs)-1)*q; lo=int(math.floor(p)); hi=int(math.ceil(p))
    return xs[lo] if lo==hi else xs[lo]+(xs[hi]-xs[lo])*(p-lo)

def write_csv(path, rows):
    if not rows:
        raise RuntimeError(f"No rows generated for {path}")
    with open(path,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="work/curated_from_raw.csv")
    ap.add_argument("--output",default="work/quality_flags_from_raw.csv")
    ap.add_argument("--zero-output",default="work/zero_semantics_review_from_raw.csv")
    args=ap.parse_args()

    with open(args.input,encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    for r in rows:
        r["_date"]=datetime.strptime(r["Controle_Date"],"%Y-%m-%d").date()
        for p in MEAS:r["_"+p]=num(r[p])

    stats={}
    for p in MEAS:
        vals=[r["_"+p] for r in rows if r["_"+p] is not None]
        stats[p]={"median":quantile(vals,.5),"p999":quantile(vals,.999)}

    flags=[]; seen=set()
    def add(r,p,code,severity,reason,prev="",nxt="",aux=""):
        k=(r["Record_ID"],p,code)
        if k in seen:return
        seen.add(k)
        flags.append({
            "Record_ID":r["Record_ID"],"Post_ID":r["Post_ID"],"Controle_Date":r["Controle_Date"],
            "Parameter":p,"Value":r["_"+p],"Flag_Code":code,"Severity":severity,
            "Reason":reason,"Previous_Value":prev,"Next_Value":nxt,
            "Post_Name":r["Post_Name"],"Riverbas_Name":r["Riverbas_Name"],
            "Source_ID":r["Source_ID"],"Source_Sheet":r["Source_Sheet"],"Auxiliary":aux
        })

    for r in rows:
        if r["_Kisen"] is not None and r["_Kisen"]>25:
            add(r,"Kisen","DQ001_DO_GT25","high","Dissolved oxygen >25 mg/dm3.")
        if r["_Simazin"] is not None and r["_Simazin"]>=1 and 2004<=r["_date"].year<=2006:
            add(r,"Simazin","DQ002_SIMAZIN_SCALE_ERA","high","2004–2006 Simazin scale discontinuity.")

    series=defaultdict(list)
    for r in rows:
        for p in MEAS:
            if r["_"+p] is not None:
                series[(r["Post_ID"],p)].append((r["_date"],r["_"+p],r))
    for k in series:
        series[k].sort(key=lambda x:x[0])

    zero_review=[]
    for (pid,p),arr in series.items():
        if len(arr)<3: continue
        for i in range(1,len(arr)-1):
            d0,v0,r0=arr[i-1]; d,v,r=arr[i]; d1,v1,r1=arr[i+1]

            # zero-semantics review: exactly the rule used for the publication candidate
            if v==0 and v0>0 and v1>0:
                if (d-d0).days<=180 and (d1-d).days<=180 and max(v0,v1)/min(v0,v1)<=5:
                    zero_review.append({
                        "Record_ID":r["Record_ID"],"Post_ID":pid,"Controle_Date":r["Controle_Date"],
                        "Parameter":p,"Zero_Value":0,"Previous_Value":v0,"Next_Value":v1,
                        "Previous_Date":d0.isoformat(),"Next_Date":d1.isoformat(),
                        "Post_Name":r["Post_Name"],"Source_Sheet":r["Source_Sheet"],
                        "Interpretation":"Zero occurs between two positive, mutually consistent observations; may be true zero, below-detection coding, or source convention. Retained unchanged."
                    })
                continue

            if min(v,v0,v1)<=0: continue
            if (d-d0).days>180 or (d1-d).days>180: continue
            nr=max(v0,v1)/min(v0,v1)
            if nr>5: continue
            center=math.sqrt(v0*v1); ratio=v/center
            ar=ratio if ratio>=1 else 1/ratio
            if ar>=20:
                k10=round(math.log10(ar))
                if nr<=3 and 2<=k10<=6 and abs(ar-10**k10)/(10**k10)<=.08:
                    add(r,p,"DQ003_DECIMAL_SHIFT_CANDIDATE","high","~100x or ~1000x isolated temporal shift.",v0,v1,f"ratio={ratio}")
                else:
                    add(r,p,"DQ005_TEMPORAL_ISOLATED_EXTREME","review",">=20-fold isolated temporal extreme.",v0,v1,f"ratio={ratio}")

    for p in MEAS:
        cut=stats[p]["p999"]; med=stats[p]["median"]
        for r in rows:
            v=r["_"+p]
            if v is not None and cut is not None and v>cut and (med==0 or (med and v>10*med)):
                add(r,p,"DQ004_GLOBAL_EXTREME_TAIL","review","Above global P99.9 and >10x median.")

    for r in rows:
        bod=r["_BSK5"]; cod=r["_HSK"]
        if bod is not None and cod is not None and bod>0 and cod<.5*bod:
            add(r,"HSK","DQ006_COD_BOD5_CONSISTENCY","review","HSK < 0.5 * BSK5.",aux=f"BSK5={bod}")

    write_csv(args.output,flags)
    write_csv(args.zero_output,zero_review)
    print(f"QC flags={len(flags)}; high={sum(x['Severity']=='high' for x in flags)}; zero-review={len(zero_review)}")

if __name__=="__main__":
    main()
