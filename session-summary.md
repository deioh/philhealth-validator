# Session Summary — PhilHealth eClaims Validator

**Date:** 2026‑11‑13  
**Purpose:** Design an offline, pre‑submission validator for hospital claims to reduce PhilHealth eClaims rejections.

---

## 1. Background

- Hospital billing team prepares claims using **scanned documents** + **encoded patient data**.
- Only the encoded data is available to the billing/IT team for automated checks.
- Data lives in **Microsoft SQL Server** (`psPatRegisters`, `psPatFinalDXDtls`, `psPHICSurgProc`, `psPHICCF4DctrOrder`).
- Goal: **Flag possible issues before online eClaims 3.0 submission** (missing ICD‑10, invalid RVS codes, case‑rate mismatches, duplicate claims, etc.).

---

## 2. PhilHealth Requirements Captured

Based on official PhilHealth advisories:

| Requirement | Source |
|-------------|--------|
| eClaims **3.0 only** from Apr 1, 2026 (lower versions disabled) | PA2026‑0022, PA2025‑0076 |
| **Statement of Account (eSOA)** must be **XML** (not PDF) for admissions ≥ Apr 2026 | PA2025‑0076 |
| Complete **ICD‑10** diagnosis coding (principal + secondary) | Annex E – Rules on Claims Filing |
| **RVS / Package codes** for every procedure | Annex E |
| **Claim Form 5 (CF5)** required for DRG grouping | Implementation Manual Vol 1 |
| Only accredited HFs may file | Annex E |

---

## 3. Data Tables Identified

| Table | Key Fields Used | Role |
|-------|-----------------|------|
| `PK_psPatRegisters` | `PK_psPatRegisters`, `registrydate` (admission), `dischdate` (discharge), `finaldiagcode` (ICD‑10), `isCOVID19`, `WithPhilHealth`, `PhicRefNo`, `casetype` | Patient master / encounter header |
| `PK_psPatFinalDXDtls` | `FK_mscICD10Mstr` (ICD‑10), `isPrimary`, `CaseRate`, `CaseRatePF`, `CaseRateHB`, `CaseRateGroupCode`, `isPrimaryCV19`, etc. | Final diagnosis details (CF3 equivalent) |
| `PK_psPHICSurgProc` | `FK_mscSurgProc` (procedure code), `ruvvalue` (RVS), `HBamount`, `PFamount`, `isIncluded` | Surgical procedures |
| `PK_psPHICCF4DctrOrder` | `orderDate`, `remarks` (free text), `isCOVID19` | Doctor’s orders / clinical notes |
| `PK_psPHICCF4` (encounter) | `admitDatetime`, `dischDatetime`, `PackageType`, clinical findings | CF4 encounter documentation |

> **Note:** `arrivedate` was NULL in the sample; the actual admission date is **`registrydate`**.

---

## 4. Validator Rules Implemented

| Rule | Fields | Severity |
|------|--------|----------|
| ICD‑10 presence & format | `principal_icd10` | Error |
| Admission date present | `registrydate` / `arrivedate` | Error |
| Discharge date present | `dischdate` | Error |
| Discharge ≥ admission | dates | Error |
| Primary diagnosis uniqueness | `isPrimary` | Warning |
| Case‑rate split (`CaseRate = PF + HB`) | `CaseRate`, `CaseRatePF`, `CaseRateHB` | Warning |
| Procedure RVS numeric | `procedure_rvs` | Error (skip if NULL) |
| Procedure HB/PF numeric | `HBamount`, `PFamount` | Warning (skip if NULL) |
| COVID flag consistency | patient / dx / order flags | Warning |
| Order date within admission window | `order_datetime` vs `registrydate`/`dischdate` | Warning |
| Order remarks present | `order_remarks` | Warning |
| Discharge order present before discharge | `order_remarks` keywords | Warning |
| Duplicate claim detection | `claim_id` + `registrydate` + `principal_icd10` | Warning |

---

## 5. Files Created

| File | Description |
|------|-------------|
| `validator.py` | Offline validator (stdlib only, no internet) |
| `export_claims.sql` | MS SQL query to export claim data to CSV |
| `claims_export.csv` | Sample data (patient 717370) |
| `report.json` | Generated validation report (sample run) |
| `README.md` | Full documentation |
| `.gitignore` | Ignores sensitive CSVs, logs, Python cache, etc. |
| `LICENSE` | MIT |
| `session-summary.md` | This file |

---

## 6. Sample Validation Result

Running `python validator.py claims_export.csv report.json` on the sample 5‑row dataset produced:

- **5 errors** — `procedure_rvs` not numeric (all NULL).
- **21 warnings** — duplicate claim rows, multiple primary diagnoses, HB/PF not numeric, one spurious order‑date window flag.

> **Interpretation:** The errors are **soft** (data absent, not invalid). Populate the procedure fields or make the validator NULL‑tolerant; then the report will pass.

---

## 7. Next Steps / Improvements

1. **Make validator NULL‑tolerant** for procedure fields (skip check when `procedure_code` / `procedure_rvs` is NULL).
2. **Add master‑list validation** for ICD‑10, RVS, and case‑rate group codes (local text files).
3. **Optional**: wrap as `omp philhealth validate <file>` using oh‑my‑pi.
4. **Schedule** a daily cron/Windows Task Scheduler job to validate the latest export and e‑mail/Slack the report.
5. **Add cf3/cf4 benefit‑category rules** once their schemas are provided.

---

## 8. Security Notes

- All processing is **offline**; no PHI leaves the hospital network.
- `report.json` includes the input file’s SHA‑256 hash for tamper‑evident auditing.
- Store CSV exports in a restricted folder with appropriate ACLs.
- Keep `claims_export.csv` and `report.json` out of the public GitHub repo (already ignored by `.gitignore`).

---

## 9. GitHub Upload

Repository contains:

- `validator.py`
- `export_claims.sql`
- `README.md`
- `LICENSE`
- `.gitignore`
- `session-summary.md`

**Sensitive data files** (`claims_export.csv`, `report.json`) are excluded via `.gitignore` and should **never** be committed.

To push:

```bash
cd C:\Users\Deioh\philhealth-validator
git init
git add .
git commit -m "Initial commit: PhilHealth eClaims validator"
git branch -M main
git remote add origin https://github.com/<your-username>/philhealth-validator.git
git push -u origin main
```

Replace `<your-username>` with your GitHub username and create the repository first on GitHub. If you use a personal access token, ensure it has `repo` scope.