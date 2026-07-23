# Session Handoff — Project 1: Diabetes Readmission Risk Model

For picking this project back up in a new session (with me or otherwise). The repo itself and `project1-build-plan.md` are the actual source of truth — this note is just a map to them.

## Where things stand

- **Portfolio context**: Project 1 of a 4-project ML portfolio (healthcare, financial-risk NLP, seismic-hazard deployment, causal inference) built to demonstrate industry-ready ML engineering for a transition from an academic science background into an ML engineer role.
- **Dataset**: switched from the originally-planned UCI diabetes dataset to **MIMIC-IV**. PhysioNet/CITI credentialing is in progress but not yet complete.
- **Scope decision (locked)**: diabetic patients only — not broadened to all-cause readmission.
- **Repo**: `/Users/sdgoddard/Google Drive/My Drive/Project support/Career planning/Projects/Project 1--Diabetes readmission`, tracked on GitHub, `main` branch, working tree currently clean.

## What's built and committed

- `README.md` — project overview, problem statement, repo structure summary
- `.gitignore` — ignores `__pycache__/`, `*.pyc`, `.venv/`, `.env`, `.DS_Store`, and `/data/` (anchored to repo root with a leading slash — an unanchored `data/` will also catch `src/data/`, which bit us once already; don't remove the leading slash)
- `requirements.txt` — pandas, scikit-learn, lightgbm, shap, fastapi, duckdb, pytest, etc.
- `sql/cohort_definition.sql` — BigQuery-flavored draft of the diabetic 30-day-readmission cohort query (diagnosis filter on ICD-9 250.xx / ICD-10 E08–E13, readmission-gap self-join on `admissions`, mortality/hospice exclusion)
- `src/data/extract.py` — DuckDB-based runnable version of the same query, **validated against the MIMIC-IV Demo dataset** (100 patients, no credentialing required, downloaded from PhysioNet)
  - Confirmed `discharge_location` values are clean exact strings (`DIED`, `HOSPICE`, etc.) — the exclusion filter needs no changes
  - Ran successfully: 105 admissions, 33 patients, 20% naive readmit rate (meaningless at n=33 — this run only validated that the pipeline executes correctly)

## Not yet done

- `project1-build-plan.md` (the full technical plan: data cleaning, feature engineering, model comparison, calibration, explainability, error analysis) exists in this chat's outputs but **has not yet been added to the repo**. The README references it at `docs/build-plan.md` — add it there to match.
- MIMIC-IV credentialing still pending — full dataset not yet accessible, everything so far is against the demo subset.
- Feature engineering, model training, calibration, explainability, error analysis, API, Docker, and deployment are all still ahead (see build plan sections 3–8).

## Next step

Feature engineering (`src/features/build_features.py`): join lab values (HbA1c, glucose, creatinine via `labevents`/`d_labitems`), medications (`prescriptions`), and prior-utilization counts onto the cohort. Full approach is in section 3 of the build plan.

## Key decisions already made (don't re-litigate these)

- MIMIC-IV over the UCI dataset, accepting the credentialing wait for richer lab/medication data
- Diabetic-only scope, not all-cause readmission
- Notes/NLP deliberately out of scope for Project 1 (kept as Project 2's differentiator)
- App Runner preferred over EC2 for eventual deployment (less infrastructure to manage for a portfolio project)
- Single GitHub repo, structured like a working ML engineer's project (see build plan section 8 for the full directory layout), not a notebook

## Working context

Scott is new to git, VSCode, Docker, and AWS, and has been learning the fundamentals hands-on as we go (stage vs. commit, `.gitignore` anchoring rules, venv activation, `python3` vs. `python` on macOS/zsh). Explanations should keep assuming that starting point rather than expert familiarity. OS is macOS, shell is zsh, editor is VSCode.
