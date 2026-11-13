#!/usr/bin/env python3
"""
PhilHealth eClaims pre-submission validator (offline).
Usage:  python validator.py claims_export.csv report.json

Note: admission date is read from 'registrydate' if present, else 'arrivedate'.
      discharge date is read from 'dischdate'.
"""
import argparse, csv, hashlib, json, re
from collections import defaultdict
from datetime import datetime

ICD10_RE = re.compile(r'^[A-Z][0-9][A-Z0-9.]{0,4}$', re.IGNORECASE)
DISCHARGE_KEYWORDS = ("discharge", "go home", "discharge order", "home meds")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_date(s):
    s = (s or "").strip()
    if not s or s.upper() == "NULL":
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def is_number(v):
    try:
        float(str(v).replace(",", "").strip() or 0)
        return True
    except ValueError:
        return False


def fnum(v):
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def truthy(v):
    return str(v).strip() in ("1", "true", "True", "YES", "Y")


def get_admission_date(row):
    """Return admission date from registrydate or arrivedate."""
    return parse_date(row.get("registrydate") or row.get("arrivedate"))


def get_discharge_date(row):
    """Return discharge date from dischdate."""
    return parse_date(row.get("dischdate"))


def validate(rows):
    errors, warnings = [], []

    # --- Dates & required dates ---
    for i, r in enumerate(rows):
        arr = get_admission_date(r)
        dis = get_discharge_date(r)
        if not arr:
            errors.append((i, "admission_date", "Missing/invalid admission date (registrydate/arrivedate)"))
        if not dis:
            errors.append((i, "dischdate", "Missing/invalid discharge date"))
        if arr and dis and dis < arr:
            errors.append((i, "dates", "Discharge before admission"))

    # --- ICD-10 validity ---
    for i, r in enumerate(rows):
        code = (r.get("principal_icd10") or "").strip()
        if not code:
            errors.append((i, "principal_icd10", "Missing principal ICD-10 code"))
        elif not ICD10_RE.match(code):
            errors.append((i, "principal_icd10", f"Malformed ICD-10 code: {code}"))

    # --- Primary diagnosis uniqueness per claim ---
    prim = defaultdict(list)
    for i, r in enumerate(rows):
        if truthy(r.get("isPrimary")):
            prim[r.get("claim_id")].append(i)
    for cid, idxs in prim.items():
        if len(idxs) > 1:
            for i in idxs:
                warnings.append((i, "isPrimary",
                    f"Multiple primary diagnoses ({len(idxs)}) for claim {cid}"))
        elif len(idxs) == 0:
            for i, r in enumerate(rows):
                if r.get("claim_id") == cid:
                    errors.append((i, "isPrimary", "No primary diagnosis flagged"))

    # --- Case-rate split: CaseRate == PF + HB ---
    for i, r in enumerate(rows):
        if all(is_number(r.get(k)) for k in ("CaseRate", "CaseRatePF", "CaseRateHB")):
            tot, pf, hb = fnum(r["CaseRate"]), fnum(r["CaseRatePF"]), fnum(r["CaseRateHB"])
            if abs(tot - (pf + hb)) > 1.0:   # allow rounding penny
                warnings.append((i, "CaseRate",
                    f"CaseRate {tot} != PF {pf} + HB {hb}"))
        else:
            warnings.append((i, "CaseRate", "CaseRate/PF/HB not numeric or missing"))

    # --- Procedure amounts ---
    for i, r in enumerate(rows):
        if r.get("procedure_code"):
            if not is_number(r.get("procedure_rvs")):
                errors.append((i, "procedure_rvs", "RVS value not numeric"))
            for k in ("HBamount", "PFamount"):
                if r.get(k) and not is_number(r.get(k)):
                    warnings.append((i, k, f"{k} not numeric"))

    # --- COVID flag consistency across patient/dx/orders ---
    for i, r in enumerate(rows):
        pt  = truthy(r.get("patient_covid_flag"))
        dx  = truthy(r.get("isPrimaryCV19")) or truthy(r.get("isIcd10CV19"))
        ord_ = truthy(r.get("order_covid_flag"))
        flags = {pt, dx, ord_}
        if len(flags) > 1 and (pt or dx or ord_):
            warnings.append((i, "isCOVID19",
                f"COVID flag mismatch: patient={pt}, diagnosis={dx}, orders={ord_}"))

    # --- Order date within admission + remarks present ---
    for i, r in enumerate(rows):
        arr = get_admission_date(r)
        dis = get_discharge_date(r)
        odt = parse_date(r.get("order_datetime"))
        if odt and arr and dis:
            if not (arr <= odt <= dis):
                warnings.append((i, "order_datetime",
                    "Order date outside admission/discharge window"))
        if not (r.get("order_remarks") or "").strip():
            warnings.append((i, "order_remarks", "Doctor order remarks are empty"))

    # --- Discharge order present before discharge (per claim) ---
    per_claim = defaultdict(lambda: {"has_discharge": False})
    for r in rows:
        cid = r.get("claim_id")
        if any(k in (r.get("order_remarks") or "").lower() for k in DISCHARGE_KEYWORDS):
            odt = parse_date(r.get("order_datetime"))
            dis = get_discharge_date(r)
            if dis and (odt is None or odt <= dis):
                per_claim[cid]["has_discharge"] = True
    for i, r in enumerate(rows):
        if not per_claim[r.get("claim_id")]["has_discharge"]:
            warnings.append((i, "discharge_order",
                "No discharge/go-home order found before discharge date"))

    # --- Duplicate claim detection (same claim + admission + dx) ---
    seen, dup = {}, set()
    for i, r in enumerate(rows):
        arr = get_admission_date(r)
        key = (r.get("claim_id"), arr.strftime("%Y-%m-%d") if arr else None, r.get("principal_icd10"))
        if key in seen:
            dup.add(seen[key])
            dup.add(i)
        else:
            seen[key] = i
    for i in sorted(dup):
        warnings.append((i, "duplicate", "Possible duplicate claim row"))

    return errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvfile")
    ap.add_argument("outjson", nargs="?", default="report.json")
    a = ap.parse_args()

    with open(a.csvfile, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    errors, warnings = validate(rows)
    report = {
        "status": "PASS" if not errors else "FAIL",
        "total_rows": len(rows),
        "total_errors": len(errors),
        "total_warnings": len(warnings),
        "errors": [{"row": i, "field": fld, "message": msg} for i, fld, msg in errors],
        "warnings": [{"row": i, "field": fld, "message": msg} for i, fld, msg in warnings],
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "file_sha256": sha256_file(a.csvfile),
    }
    with open(a.outjson, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()