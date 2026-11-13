# PhilHealth eClaims Pre-Submission Validator

Offline validator for hospital claims before online PhilHealth eClaims 3.0 submission. Checks encoded claim data against PhilHealth requirements (Annex E, eClaims 3.0 advisories) so billing teams catch issues *before* they hit the portal.

## Purpose

- Run entirely on your local server — no PHI leaves your network.
- Validate ICD‑10 codes, RVS/Package procedure codes, case‑rate amounts, admission/discharge dates, doctor‑order documentation, COVID‑19 flags, and duplicate claims.
- Outputs a color-coded JSON report (`report.json`) with errors, warnings, and an audit‑trail (file SHA‑256 hash).

## Supported Data Model

| Table | Source File / Schema | What It Covers |
|-------|----------------------|----------------|
| `psPatRegisters` | `PK_psPatRegisters` | Patient master — PhilHealth ID, admission (`registrydate`), discharge (`dischdate`), final ICD‑10 code (`finaldiagcode`), COVID flag, etc. |
| `psPatFinalDXDtls` | `PK_psPatFinalDXDtls` | Final diagnosis details — ICD‑10 master code, case‑rate amounts, primary flag, group code, etc. |
| `psPHICSurgProc` | `PK_psPHICSurgProc` | Procedure codes — RVS value, HB/PF amounts, included flag, etc. |
| `psPHICCF4DctrOrder` | `PK_psPHICCF4DctrOrder` | Doctor’s orders — order date, remarks, COVID flag, etc. |

## Files

| File | Description |
|------|-------------|
| `export_claims.sql` | MS SQL query to extract claim data from your hospital database. Export result to `claims_export.csv`. |
| `validator.py` | Offline Python validator. Reads `claims_export.csv`, runs rule checks, writes `report.json`. |
| `claims_export.csv` | Example input file (sample patient 717370). Replace with your actual export. |
| `report.json` | Generated validation report (status, errors, warnings, file SHA‑256, timestamp). |
| `LICENSE` | MIT License (optional — remove if you prefer internal use only). |
| `.gitignore` | Git ignore rules for Python/SQL projects. |

## Quick Start

### 1. Export data from MS SQL

Open `export_claims.sql` in SQL Server Management Studio (SSMS) or any SQL client:

```sql
SET NOCOUNT ON;
SELECT
    p.PK_psPatRegisters              AS claim_id,
    CONVERT(varchar(10), p.registrydate, 23) AS registrydate,
    CONVERT(varchar(10), p.dischdate,  23) AS dischdate,
    p.finaldiagcode                  AS principal_icd10,
    p.isWithPhilHealth,
    p.PhicRefNo,
    p.casetype,
    p.isCOVID19                      AS patient_covid_flag,
    d.isPrimary,
    d.CaseRate,
    d.CaseRatePF,
    d.CaseRateHB,
    d.CaseRateGroupCode,
    d.isFirstCaseRate                AS dx_first_case_rate,
    d.isSecondCaseRate               AS dx_second_case_rate,
    d.isPrimaryCV19,
    d.isIcd10CV19,
    s.FK_mscSurgProc                 AS procedure_code,
    s.ruvvalue                       AS procedure_rvs,
    s.HBamount,
    s.PFamount,
    s.isIncluded,
    o.orderDate                      AS order_datetime,
    o.remarks                        AS order_remarks,
    o.isCOVID19                      AS order_covid_flag
FROM   dbo.psPatRegisters        p
LEFT JOIN dbo.psPatFinalDXDtls   d
       ON d.FK_psPatRegisters = p.PK_psPatRegisters
LEFT JOIN dbo.psPHICSurgProc     s
       ON s.fk_psPatRegisters = p.PK_psPatRegisters
LEFT JOIN dbo.psPHICCF4DctrOrder o
       ON o.FK_psPatRegisters = p.PK_psPatRegisters
WHERE  p.PK_psPatRegisters = 717370;
```

Export the result set to **`claims_export.csv`** (UTF‑8, comma‑separated).

### 2. Run the validator

```bash
cd C:\Users\Deioh\philhealth-validator
python validator.py claims_export.csv report.json
```

### 3. Review the report

Open `report.json`:

```json
{
  "status": "PASS",
  "total_rows": 1,
  "total_errors": 0,
  "total_warnings": 0,
  "errors": [],
  "warnings": [],
  "generated_at": "2026-04-01T12:00:00Z",
  "file_sha256": "..."
}
```

- `status = "PASS"` → no blocking errors; claim is clean for submission.
- `status = "FAIL"` → fix the listed errors before submitting.
- `warnings` → informational items (duplicates, missing optional fields, etc.).

## Validation Rules

| Rule | Field(s) Checked | Severity |
|------|------------------|----------|
| Principal ICD‑10 presence & format | `principal_icd10` | Error |
| Admission date present | `registrydate` / `arrivedate` | Error |
| Discharge date present | `dischdate` | Error |
| Discharge ≥ admission | `registrydate`, `dischdate` | Error |
| Primary diagnosis uniqueness | `isPrimary` per claim | Warning |
| Case‑rate split: `CaseRate = PF + HB` | `CaseRate`, `CaseRatePF`, `CaseRateHB` | Warning |
| Procedure RVS numeric | `procedure_rvs` | Error (skip if NULL) |
| Procedure HB/PF amounts numeric | `HBamount`, `PFamount` | Warning (skip if NULL) |
| COVID flag consistency | `patient_covid_flag`, `isPrimaryCV19`, `isIcd10CV19`, `order_covid_flag` | Warning |
| Order date within admission window | `order_datetime` vs `registrydate`/`dischdate` | Warning |
| Order remarks present | `order_remarks` | Warning |
| Discharge order present before discharge | `order_remarks` contains "discharge"/"go home" | Warning |
| Duplicate claim detection | `claim_id` + `registrydate` + `principal_icd10` | Warning |

## Customization

Edit `validator.py` to:

- Adjust severity (error vs warning).
- Add new master lists (ICD‑10, RVS, case‑rate group codes).
- Add business-specific rules (e.g., Z‑benefits, COVID‑19 specific case rates).

## Security & Compliance

- **No internet calls.** All checks run locally on your machine.
- **No PHI transmission.** The script reads local CSV files only.
- **Audit trail.** `report.json` logs SHA‑256 hash of the input CSV, timestamp, error counts, and field-level details.
- Store `claims_export.csv` and `report.json` in a restricted folder with appropriate access controls.

## Requirements

- Python 3.8+ (standard library only — `csv`, `json`, `re`, `argparse`, `hashlib`, `datetime`)
- Microsoft SQL Server (for the export query)
- Network share or local disk access to `export_claims.sql` output directory

## License

MIT License. See `LICENSE` for details.

## Disclaimer

This tool assists with pre-submission validation. It does not replace PhilHealth’s official validation engine, provider accreditation checks, or real-time eligibility verification. Always consult the latest PhilHealth circulars (e.g., PA2025‑0076, PA2026‑0022) for current eClaims 3.0 requirements.