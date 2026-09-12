"""Common parser and curation utilities for the Ukrainian surface-water dataset."""
from __future__ import annotations
import csv, hashlib, re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXCEL_EPOCH = datetime(1899,12,30)
MONTHS_UA = {
    "Січ":1,"Лют":2,"Бер":3,"Кві":4,"Тра":5,"Чер":6,
    "Лип":7,"Сер":8,"Вер":9,"Жов":10,"Лис":11,"Гру":12,
}
CHEM_FIELDS = [
    "Azot","BSK5","Zavisli","Kisen","Sulfat","Hlorid","Amoniy",
    "Nitrat","Nitrit","Fosfat","SPAR","Permanganat","HSK"
]
MEASUREMENT_FIELDS = CHEM_FIELDS + ["Fitoplan","Atrazin","Simazin"]
DECIMAL_FIELDS = ["Latitude","Longitude"] + MEASUREMENT_FIELDS
TEXT_FIELDS = ["Post_Name","Post_Code","Riverbas_Name","WaterLab_Name"]

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def load_schema(path: Path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def repair_semicolon_row(parts, expected_fields=24):
    """Repair structural semicolon(s) inside Post_Name by right-anchoring the last 22 fields."""
    original=list(parts)
    # Some source files contain a terminal delimiter.
    while len(parts)>expected_fields and parts and parts[-1]=="":
        parts=parts[:-1]
    if len(parts)==expected_fields:
        return parts, None
    if len(parts)>expected_fields:
        # Structure is: Post_ID | Post_Name | 22 remaining fields.
        tail_count=22
        name_parts=parts[1:len(parts)-tail_count]
        if len(name_parts)<2:
            raise ValueError(f"Cannot repair row with {len(original)} fields")
        repaired_name=", ".join(x.strip() for x in name_parts if x is not None).strip()
        fixed=[parts[0],repaired_name]+parts[len(parts)-tail_count:]
        if len(fixed)!=expected_fields:
            raise ValueError(f"Repair produced {len(fixed)} fields")
        return fixed,{
            "raw_field_count":len(original),
            "post_id":parts[0],
            "name_fragments":" | ".join(name_parts),
            "repaired_post_name":repaired_name,
        }
    raise ValueError(f"Short row: {len(parts)} fields, expected {expected_fields}")

def parse_raw_csv(path: Path, source_id: str, source_sheet: str, schema_fields):
    rows=[]; structural=[]
    with path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.reader(f,delimiter=";",quotechar='"')
        header=next(reader)
        while header and header[-1]=="":
            header=header[:-1]
        if header[:len(schema_fields)]!=schema_fields:
            # tolerate only a terminal technical empty column
            if header!=schema_fields:
                raise ValueError(f"{path.name}: unexpected header {header}")
        for line_no, parts in enumerate(reader,start=2):
            if not parts or all(x=="" for x in parts):
                continue
            fixed, repair=repair_semicolon_row(parts,len(schema_fields))
            rec=dict(zip(schema_fields,fixed))
            rec["Source_ID"]=source_id
            rec["Source_Sheet"]=source_sheet
            rec["_source_line"]=line_no
            rows.append(rec)
            if repair:
                repair.update({"Source_ID":source_id,"Source_Sheet":source_sheet,"Source_Line":line_no})
                structural.append(repair)
    return rows, structural

def repair_text_date_autoconversion(value):
    s=value.strip()
    m=re.fullmatch(r"(\d{1,2})\.("+"|".join(MONTHS_UA)+r")",s)
    if m:
        left=int(m.group(1)); month=MONTHS_UA[m.group(2)]
        return f"{left}.{month:02d}","DD.MMM -> DD.MM"
    m=re.fullmatch(r"("+"|".join(MONTHS_UA)+r")\.(\d{1,2})",s)
    if m:
        month=MONTHS_UA[m.group(1)]; yy=int(m.group(2))
        return f"{month}.{yy:02d}","MMM.YY -> MM.YY"
    return None,None

def repair_numeric_excel_serial(value, field, observation_date):
    """Return corrected string only when the serial-date interpretation is structurally supported."""
    if field not in CHEM_FIELDS:
        return None,None
    s=value.strip()
    try:
        d=Decimal(s)
    except InvalidOperation:
        return None,None
    if d != d.to_integral_value():
        return None,None
    serial=int(d)
    if not (10959 <= serial <= 60000):
        return None,None
    decoded=(EXCEL_EPOCH+timedelta(days=serial)).date()
    obs=datetime.strptime(observation_date,"%Y-%m-%d").date()
    # Same observation year -> DD.MM, including first day of month.
    if decoded.year==obs.year:
        return f"{decoded.day}.{decoded.month:02d}",f"Excel serial {serial} -> {decoded.isoformat()} -> DD.MM"
    # A date on day 1 in another year can arise from MM.YY input, e.g. 10.56.
    if decoded.day==1:
        return f"{decoded.month}.{decoded.year%100:02d}",f"Excel serial {serial} -> {decoded.isoformat()} -> MM.YY"
    return None,None

def normalize_control_date(value):
    """Normalize supported source date formats to ISO 8601 YYYY-MM-DD.

    The official source files are not fully uniform across years. Historical
    CSV resources use DD.MM.YYYY (for example, 14.04.2020), while some later
    curated/source tables use YYYY-MM-DD. Only these two explicit formats are
    accepted; unexpected date formats fail closed.
    """
    s=(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s,fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(
        f"Unsupported Controle_Date format: {s!r}; expected YYYY-MM-DD or DD.MM.YYYY"
    )

def curate_record(raw, schema_fields):
    r={k:raw.get(k,"") for k in schema_fields}
    corrections=[]
    # identifiers / text
    r["Post_ID"]=str(r["Post_ID"]).strip()
    for field in TEXT_FIELDS:
        val=(r[field] or "").strip()
        r[field]="" if val.upper()=="NULL" else val
    # Normalize the official source date to ISO 8601.
    dt=normalize_control_date(r["Controle_Date"])
    r["Controle_Date"]=dt

    for field in DECIMAL_FIELDS:
        rawv=(r[field] or "").strip()
        if rawv=="" or rawv.upper()=="NULL":
            r[field]=""
            continue
        corrected,rule=repair_text_date_autoconversion(rawv)
        code=None
        if corrected is not None:
            code="TC001_TEXT_DATE_AUTOCONVERSION"
        else:
            corrected,rule=repair_numeric_excel_serial(rawv,field,dt)
            if corrected is not None:
                code="TC002_NUMERIC_EXCEL_SERIAL_AUTOCONVERSION"
        if corrected is not None:
            r[field]=corrected
            corrections.append({
                "Field":field,"Correction_Code":code,"Original_Value":rawv,
                "Corrected_Value":corrected,"Correction_Rule":rule
            })
        else:
            # Decimal validation only; preserve source textual precision.
            Decimal(rawv)
            r[field]=rawv
    r["Source_ID"]=raw["Source_ID"]
    r["Source_Sheet"]=raw["Source_Sheet"]
    r["Record_ID"]=f"SWM_{r['Post_ID']}_{r['Controle_Date'].replace('-','')}"
    return r,corrections

def canonical_content_hash(records, schema_fields):
    lines=[]
    for r in sorted(records,key=lambda x:x["Record_ID"]):
        lines.append("\x1f".join(r.get(k,"") for k in schema_fields))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
