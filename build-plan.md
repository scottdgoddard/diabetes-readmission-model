# Project 1 Build Plan: Diabetes 30-Day Readmission Risk Model (MIMIC-IV)

Dataset: **MIMIC-IV**, hospital-wide (`hosp`) module — recommended over MIMIC-III since it's more recent, better documented, and its `hosp` module already covers all hospital admissions (not just ICU), which is the closer analog to the original UCI cohort. ICU-specific tables (`icu` module) are an optional feature-enrichment source for patients who had an ICU stay, not the primary cohort definition.

Yes — switching datasets changes several sections below. Model comparison, calibration methodology, and explainability approach stay conceptually the same; data acquisition, cleaning, cohort definition, and feature engineering change substantially because MIMIC is a relational multi-table EHR extract, not a single pre-cleaned CSV.

## 0\. Access and timeline

- Credentialing: complete the CITI "Data or Specimens Only Research" course, then apply for PhysioNet credentialed access, then sign the MIMIC-IV data use agreement. This is a review queue, not instant — budget for it running in parallel with other work, not as a blocking dependency for everything.  
- Access options once credentialed: direct CSV.gz download from PhysioNet, or query via Google BigQuery (`physionet-data.mimiciv_hosp.*`, `physionet-data.mimiciv_icu.*`) which avoids downloading the larger tables (`labevents`, `chartevents` are very large) locally. Given the AWS-based deployment target in the handoff, plan to do cohort extraction/aggregation in BigQuery or a local Postgres/DuckDB instance, then move only the resulting modeling table to the AWS pipeline — not the raw MIMIC tables.  
- **While waiting on credentialing**: the cohort-definition and ETL logic below can be fully designed and pseudocoded against the public schema docs now, so the only thing blocked is actually running it against real data.

## 1\. Cohort definition (new step — UCI dataset had this built in)

MIMIC has no pre-packaged "diabetic encounter" table or `readmitted` column — both need to be constructed:

- **Diabetic cohort**: filter `admissions`/`patients` to encounters with a diabetes diagnosis in `diagnoses_icd` (ICD-9 codes 250.xx and ICD-10 codes E08–E13, since MIMIC-IV spans both coding eras — the cutover happened partway through the data's date range, so both need to be matched, not just one).  
- **30-day readmission target**: not a column — construct it by self-joining `admissions` on `subject_id`, sorting by `admittime`, and computing the gap between one discharge (`dischtime`) and the patient's next `admittime`. Flag \<30 days as positive.  
- **Mortality exclusion**: exclude admissions where the patient died during the stay (`deathtime` populated / `hospital_expire_flag` \= 1\) or where `discharge_location` indicates hospice — same logic as the UCI plan's "expired" exclusion, just sourced from different fields.  
- **Decide scope now**: keep the project framed as "diabetic patient readmission" (closer to the original UCI framing, keeps continuity with the write-up already planned) rather than broadening to all-cause readmission. Worth confirming this is still the intent before building, since MIMIC would just as easily support a general readmission model.

## 2\. Data acquisition and cleaning

- Core tables: `patients` (demographics, `anchor_age` — note MIMIC-IV date-shifts admission dates per patient for de-identification, but ages are preserved relative to a fixed anchor year per patient, and ages over 89 are handled specially — check the current `patients` table documentation for the exact capping rule before using age as a feature), `admissions` (admission/discharge times, admission type, insurance, race/ethnicity, discharge location, `deathtime`), `diagnoses_icd` \+ `d_icd_diagnoses` (billed diagnoses), `labevents` \+ `d_labitems` (lab results — this is where real lab values become available, unlike the UCI dataset's near-absence of labs), `prescriptions` (actual medication orders, richer than UCI's per-drug up/down/steady flags).  
- ICD-9/ICD-10 mixing: same diagnosis-grouping approach as the UCI plan (circulatory, respiratory, digestive, diabetes, injury, musculoskeletal, genitourinary, neoplasms, other), but the grouping logic needs to handle both code systems and map them to the same category scheme.  
- Table sizes: `labevents` and `chartevents` are large — do aggregation (e.g., last/mean/worst value per admission for key labs like HbA1c, glucose, creatinine) in BigQuery/Postgres rather than pulling raw event-level rows into pandas.  
- Patient-level split still applies, using `subject_id` (same leakage concern as before — a patient can have many admissions).

## 3\. Feature engineering (materially richer than UCI)

- **Real lab values** instead of the UCI dataset's binary "A1c tested / not tested" flag: pull actual HbA1c, glucose, creatinine, BUN, hemoglobin, sodium/potassium values (via `d_labitems` lookup) and engineer admission-level summaries (last value before discharge, min/max/mean during stay, delta from admission to discharge).  
- **Medications**: use `prescriptions` for actual diabetes medication classes ordered during the stay, plus counts of distinct medications — more granular than UCI's fixed drug-column list.  
- **Prior utilization**: derive prior admission count and days-since-last-discharge per patient from `admissions` history, same concept as UCI's `number_inpatient`/`number_emergency` but computed rather than given.  
- **Demographics**: race/ethnicity and insurance type available in `admissions`; gender and age in `patients`.  
- **Note module (optional, deliberately out of scope for now)**: MIMIC-IV's `discharge` notes could support NLP feature engineering, but that overlaps with Project 2's transformer/NLP focus — recommend keeping Project 1 tabular-only to preserve the portfolio's differentiation between projects, and flag notes as a stretch/future addition if time allows.

## 4\. Model comparison — unchanged in approach

Same three models (logistic regression, random forest, gradient boosting), same patient-level CV via `subject_id`, same class-weighting approach to imbalance (avoid synthetic oversampling for the same calibration reasons as before). The feature set is just richer now, so expect real lab values and prescription-derived features to compete with prior-utilization counts for top importance, versus UCI where prior utilization dominated by default due to limited lab data.

## 5\. Calibration — unchanged in approach

Same reliability diagrams, Brier score, and Platt vs. isotonic comparison on a held-out calibration set, split at the patient level. No change in methodology; richer, more clinically realistic features may make the reliability curves easier to reason about in the write-up (real lab trends vs. a binary "was A1c ever tested" flag).

## 6\. Explainability — unchanged in approach

Same SHAP approach. The richer lab/medication features should produce more clinically legible SHAP outputs than UCI's coarser fields (e.g., "rising creatinine \+ discharge on unchanged insulin dose" is a more concrete clinical story than UCI's blunter proxies).

## 7\. Error analysis — unchanged in approach

Same subgroup breakdown across race, gender, and age, same framing around Obermeyer et al. (2019). MIMIC's race/ethnicity field has more granular categories than UCI's, so the subgroup breakdown can be more detailed, though also check subgroup sample sizes before over-interpreting small strata.

## Suggested build order (revised)

1. **Today**: start CITI training / PhysioNet credentialing application.  
2. While waiting: design and pseudocode the cohort-definition query (diabetic filter \+ readmission target construction \+ mortality exclusion) against the public schema docs, and confirm the "diabetic-only vs. all-cause readmission" scope decision above.  
3. Once credentialed: run cohort extraction in BigQuery or local Postgres/DuckDB; build the aggregated admission-level modeling table (labs, meds, prior utilization, demographics).  
4. Feature engineering \+ encoding pipeline.  
5. Train logistic regression, random forest, gradient boosting on identical patient-level splits.  
6. Calibration analysis \+ comparison of calibration methods.  
7. SHAP explainability on the best-calibrated model.  
8. Error analysis \+ subgroup fairness breakdown.  
9. Write-up for a hospital care-management stakeholder; wrap in FastAPI \+ Docker; deploy to EC2 or App Runner.

Sources:

- [PhysioNet FAQs](https://physionet.org/about/faqs/)  
- [CITI Course Instructions — PhysioNet](https://physionet.org/about/citi-course/)  
- [MIMIC-IV Hosp module — MIT MIMIC docs](https://mimic.mit.edu/docs/iv/modules/hosp/)  
- [MIMIC-IV schema overview — MIT MIMIC docs](https://mimic.mit.edu/docs/IV/about/schema-overview.html)

