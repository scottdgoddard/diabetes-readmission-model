# Diabetes 30-Day Readmission Risk Model

**Status:** early development — MIMIC-IV credentialing pending, prototyping against the public MIMIC-IV Demo (100 patients) in the meantime.

## Problem

Predict, at the time a diabetic patient is discharged, whether they're likely to be readmitted to the hospital within 30 days — and do it in a way a hospital care-management team could actually trust and act on, not just a model that scores well on paper.

This means the project cares about three things most tutorial-level versions of this problem skip:

- **Calibration**: predicted probabilities need to mean what they say (a 20% predicted risk should correspond to roughly 1 in 5 similar patients actually being readmitted), not just rank patients correctly.
- **Explainability**: a clinician needs to see *why* a patient is flagged as high-risk, not just a black-box score.
- **Subgroup fairness**: performance and calibration are checked across race, age, and gender, not just in aggregate.

## Dataset

[MIMIC-IV](https://mimic.mit.edu/) hospital-wide (`hosp`) module, filtered to diabetic patients. Credentialed access via PhysioNet is in progress; development currently uses the openly-available [MIMIC-IV Clinical Database Demo](https://physionet.org/content/mimic-iv-demo/2.2/) to build and validate the pipeline ahead of full data access.

## Approach

Three tabular models — logistic regression, random forest, gradient boosting — compared on identical patient-level train/test splits, with calibration, SHAP-based explainability, and subgroup error analysis as first-class deliverables rather than afterthoughts.

## Repo structure

See [`docs/build-plan.md`](docs/build-plan.md) for the full project plan, or the summary below:

```
├── sql/            # cohort definition & feature extraction queries
├── src/
│   ├── data/       # extraction & cleaning
│   ├── features/   # feature engineering pipeline
│   ├── models/      # training, calibration, prediction
│   ├── evaluation/ # metrics, SHAP explainability, fairness audit
│   └── api/        # FastAPI serving layer
├── tests/
├── notebooks/      # exploratory analysis only
├── models/         # serialized trained models
├── reports/        # figures, model card, stakeholder write-up
└── infra/          # AWS deployment config
```

## Tech stack

Python · FastAPI · Docker · AWS App Runner · GitHub Actions

## Context

Project 1 of a 4-project ML portfolio spanning healthcare, financial risk, and causal inference, built to demonstrate industry-ready ML engineering (not just modeling) for a transition into an ML engineer role.