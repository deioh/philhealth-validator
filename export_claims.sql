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