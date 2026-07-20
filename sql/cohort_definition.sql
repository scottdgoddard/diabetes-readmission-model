-- cohort_definition.sql
--
-- Defines the diabetic 30-day readmission cohort from MIMIC-IV (hosp module).
--
-- Table references below use BigQuery naming (`physionet-data.mimiciv_hosp.*`).
-- If querying a local Postgres/DuckDB copy instead, drop the `physionet-data.`
-- project prefix and use your local schema name (e.g. mimiciv_hosp.admissions),
-- and swap DATETIME_DIFF for the equivalent date-subtraction syntax for your
-- engine (e.g. `dischtime::date - admittime::date` in Postgres).
--
-- TODO before trusting this against real data: confirm the exact
-- discharge_location string values against the current MIMIC-IV data
-- dictionary / the demo dataset -- the hospice/death category labels have
-- changed slightly across MIMIC-IV versions.

-- Step 1: diabetic admissions (any diabetes diagnosis on the encounter,
-- ICD-9 250.xx or ICD-10 E08-E13 -- MIMIC-IV spans both coding eras)
WITH diabetic_admissions AS (
  SELECT DISTINCT d.subject_id, d.hadm_id
  FROM `physionet-data.mimiciv_hosp.diagnoses_icd` d
  WHERE
    (d.icd_version = 9 AND d.icd_code LIKE '250%')
    OR (d.icd_version = 10 AND SUBSTR(d.icd_code, 1, 3) BETWEEN 'E08' AND 'E13')
),

-- Step 2: admission-level detail, restricted to the diabetic cohort
admissions_base AS (
  SELECT
    a.subject_id,
    a.hadm_id,
    a.admittime,
    a.dischtime,
    a.deathtime,
    a.hospital_expire_flag,
    a.discharge_location,
    a.admission_type,
    a.race,
    a.insurance
  FROM `physionet-data.mimiciv_hosp.admissions` a
  INNER JOIN diabetic_admissions da
    ON a.subject_id = da.subject_id AND a.hadm_id = da.hadm_id
),

-- Step 3: exclude admissions ending in death or hospice discharge.
-- A patient who died cannot be "readmitted" -- same fix as the UCI
-- dataset's expired/hospice exclusion, just sourced from different fields.
eligible_admissions AS (
  SELECT *
  FROM admissions_base
  WHERE
    deathtime IS NULL
    AND hospital_expire_flag = 0
    AND UPPER(discharge_location) NOT LIKE '%HOSPICE%'
    AND UPPER(discharge_location) NOT LIKE '%DIED%'
),

-- Step 4: find each patient's NEXT admission (any cause) to compute the
-- 30-day readmission label
with_next_admission AS (
  SELECT
    e.*,
    LEAD(e.admittime) OVER (
      PARTITION BY e.subject_id ORDER BY e.admittime
    ) AS next_admittime
  FROM eligible_admissions e
)

SELECT
  subject_id,
  hadm_id,
  admittime,
  dischtime,
  admission_type,
  race,
  insurance,
  next_admittime,
  DATETIME_DIFF(next_admittime, dischtime, DAY) AS days_to_next_admission,
  CASE
    WHEN next_admittime IS NOT NULL
     AND DATETIME_DIFF(next_admittime, dischtime, DAY) <= 30
    THEN 1 ELSE 0
  END AS readmitted_30d
FROM with_next_admission
ORDER BY subject_id, admittime;