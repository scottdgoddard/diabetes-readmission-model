# Handoff: Project 1 — Diabetes Readmission Risk Model

## Context

I'm building a 4-project ML portfolio to retrain as a machine learning engineer, moving from an academic science background into industry. I'm targeting jobs in **healthcare**, **financial risk**, and **modern causal inference**. Each project anchors a different piece of that story:

1. **Project 1 (this one): Diabetes readmission risk** — classical tabular ML, healthcare-anchored  
2. **Project 2: 10-K risk-factor NLP** — Transformer-based, financial-risk-anchored (predicting risk outcomes from SEC filing language, e.g. FinBERT fine-tuning or year-over-year risk-factor language-change detection, using the free SEC EDGAR full-text API, coverage since 2001\)  
3. **Project 3: Seismic hazard nowcasting** — end-to-end deployed ML system (training pipeline, serving, monitoring, Docker, cloud), using the live USGS earthquake feed  
4. **Project 4: TBD, explicitly causal** — likely a treatment-effect question layered on top of either the healthcare or financial domain (e.g., does a specific intervention causally reduce readmission/default, and for whom — S-/T-/X-learner or causal forest). Decide domain later.

I have a science background (not business), so all projects are deliberately framed as business/industry case studies rather than research papers, to signal I can operate in an industry context. I also intentionally lean toward projects with a slightly unusual or non-generic angle rather than the most common portfolio choices (e.g., not customer churn).

## Project 1 goal

A classical tabular prediction system comparing logistic regression, random forest, and likely gradient boosting, built around **hospital readmission risk** — specifically 30-day readmission prediction.

**Dataset**: UCI "Diabetes 130-US Hospitals for Years 1999–2008" dataset (\~100k encounters, real de-identified EHR-derived data: labs, diagnoses, medications, demographics, prior utilization). This is the practical default.

- Stretch option to discuss: MIMIC-III/IV via PhysioNet for more prestigious, more realistic clinical data — requires completing a CITI human-subjects/data-use training course for credentialed access. Worth deciding early whether to pursue this, since credentialing takes time; if pursued, it's also a genuine signal to healthcare employers that I understand clinical data governance.

## Required components (the accompanying write-up must cover)

- **Feature engineering**: from raw EHR-style fields (labs, diagnosis codes, medication changes, prior visit counts, etc.)  
- **Model comparison**: logistic regression, random forest, likely gradient boosting, with honest justification for what each buys you  
- **Calibration**: well-calibrated probabilities matter here the way they matter in clinical decision support — this section should be genuinely substantive, not a footnote (e.g., reliability diagrams, Brier score, Platt scaling vs. isotonic regression, and a discussion of why calibration matters more than raw AUC for this use case)  
- **Explainability**: SHAP or comparable, framed around what a clinician/care-management stakeholder would actually need to trust and act on a prediction  
- **Error analysis**: where the model fails and why, ideally including a fairness/disparate-impact-style breakdown across patient subgroups, since that's a real concern in clinical risk models and translates directly to the "financial risk" audience too (regulatory scrutiny of subgroup performance is common to both domains)

## Technologies

* Python  
* FastAPI  
* Docker  
* AWS EC2 **or** AWS App Runner  
* GitHub Actions (optional)

## Framing notes

- Write this as if for an internal stakeholder (e.g., a hospital care-management or population-health team deciding who gets a post-discharge intervention), not as an academic exercise.  
- The calibration/explainability rigor built here should be reusable later for Project 4 (causal), since trustworthy causal effect estimates depend on well-calibrated, interpretable outcome/propensity models. Worth noting this connection in the write-up as forward-looking context, even though the causal question itself is out of scope for Project 1\.

## What I need from you

Help me build out the concrete plan for this project: data acquisition and cleaning steps, the specific feature engineering approach, model training/comparison plan, calibration method selection, explainability approach, and how to structure the error analysis section — then help me actually build it.  
