"""
src/features/build_features.py

Builds the modeling feature table for the diabetic 30-day-readmission cohort
(output of src/data/extract.py), joining Elixhauser comorbidities, key lab
values, diabetes medication flags, prior hospital utilization, and
demographics onto each admission.

Usage:
    python src/features/build_features.py \
        --data-dir data/raw/mimic-iv-demo/hosp \
        --cohort data/interim/cohort.parquet \
        --gem data/external/icd9toicd10cmgem.csv \
        --out data/interim/features.parquet

Elixhauser comorbidities are derived via hcuppy, a Python implementation of
AHRQ's Elixhauser Comorbidity Software -- but hcuppy only ships an ICD-10-CM
mapping, and MIMIC-IV spans both coding eras (roughly half of this cohort's
admissions are ICD-9-coded, from before the hospital's ICD-10 cutover). ICD-9
diagnosis codes are therefore translated to their ICD-10-CM equivalent via
CMS's General Equivalence Mapping (GEM, sourced from NBER's processed copy)
before being run through hcuppy. MIMIC-IV also has no present-on-admission
flag, so this comorbidity count can't distinguish pre-existing conditions
from complications that developed during the stay -- a limitation to name in
the write-up, not something this script can fix.
"""

import argparse
import re
from pathlib import Path

import duckdb
import pandas as pd
from hcuppy.elixhauser import ElixhauserEngine


# MIMIC-IV carries more than one itemid for the same blood-chemistry analyte
# (different lab-feed sources). Confirmed against the demo d_labitems table;
# re-check against the full dataset once credentialed access comes through.
LAB_ITEMIDS = {
    "hba1c": [50852],  # "% Hemoglobin A1c" -- not 50854 "Absolute A1c", a different unit
    "glucose": [50931, 52569],
    "creatinine": [50912, 52546],
}

# Matched case-insensitively against prescriptions.drug. The insulin pattern
# excludes "...for Hyperkalemia" -- insulin is also given to treat high
# potassium, unrelated to diabetes management, and would otherwise be
# misclassified as a diabetes medication.
ON_INSULIN_SQL = "lower(drug) LIKE '%insulin%' AND lower(drug) NOT LIKE '%hyperkalemia%'"
ON_METFORMIN_SQL = "lower(drug) LIKE '%metformin%'"
ON_SULFONYLUREA_SQL = "regexp_matches(lower(drug), 'glipizide|glyburide|glimepiride')"


def _register_views(con: duckdb.DuckDBPyConnection, data_dir: Path) -> None:
    for table in ["admissions", "patients", "diagnoses_icd", "labevents", "prescriptions"]:
        con.execute(f"""
            CREATE OR REPLACE VIEW {table} AS
            SELECT * FROM read_csv_auto('{data_dir}/{table}.csv.gz')
        """)


def _load_gem_lookup(gem_path: Path) -> dict[str, str]:
    gem = pd.read_csv(gem_path, dtype=str)
    gem["icd9cm"] = gem["icd9cm"].str.strip()
    gem["icd10cm"] = gem["icd10cm"].str.strip()
    gem = gem.sort_values("approximate")  # exact matches (approximate == "0") first
    return gem.drop_duplicates("icd9cm", keep="first").set_index("icd9cm")["icd10cm"].to_dict()


def build_comorbidity_features(con: duckdb.DuckDBPyConnection, gem_path: Path) -> pd.DataFrame:
    dx = con.execute("""
        SELECT c.hadm_id, d.icd_code, d.icd_version
        FROM cohort c
        JOIN diagnoses_icd d ON d.hadm_id = c.hadm_id
    """).df()

    gem_lookup = _load_gem_lookup(gem_path)

    def to_icd10(row) -> str | None:
        code = row["icd_code"].strip().upper().replace(".", "")
        if row["icd_version"] == 10:
            return code
        return gem_lookup.get(code)

    dx["icd10_code"] = dx.apply(to_icd10, axis=1)
    unmapped = dx["icd10_code"].isna().sum()
    if unmapped:
        print(f"Warning: {unmapped} diagnosis codes had no ICD-9->ICD-10 GEM mapping and were dropped")
    dx = dx.dropna(subset=["icd10_code"])

    engine = ElixhauserEngine()
    categories = sorted(engine.weights["rdmsn"].keys())

    rows = []
    for hadm_id, group in dx.groupby("hadm_id"):
        result = engine.get_elixhauser(group["icd10_code"].tolist())
        present = set(result["cmrbdt_lst"])
        rows.append({"hadm_id": hadm_id, **{f"elix_{cat.lower()}": cat in present for cat in categories}})

    return pd.DataFrame(rows)


def build_lab_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    features = None
    for lab_name, itemids in LAB_ITEMIDS.items():
        itemid_list = ",".join(str(i) for i in itemids)
        lab_df = con.execute(f"""
            SELECT le.hadm_id, le.valuenum AS {lab_name}_last
            FROM labevents le
            JOIN cohort c ON le.hadm_id = c.hadm_id
            WHERE le.itemid IN ({itemid_list})
              AND le.charttime <= c.dischtime
              AND le.valuenum IS NOT NULL
            QUALIFY ROW_NUMBER() OVER (PARTITION BY le.hadm_id ORDER BY le.charttime DESC) = 1
        """).df()
        features = lab_df if features is None else features.merge(lab_df, on="hadm_id", how="outer")
    return features


def build_medication_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(f"""
        SELECT
            p.hadm_id,
            COUNT(DISTINCT p.drug) AS n_distinct_medications,
            BOOL_OR({ON_INSULIN_SQL}) AS on_insulin,
            BOOL_OR({ON_METFORMIN_SQL}) AS on_metformin,
            BOOL_OR({ON_SULFONYLUREA_SQL}) AS on_sulfonylurea
        FROM prescriptions p
        JOIN cohort c ON p.hadm_id = c.hadm_id
        GROUP BY p.hadm_id
    """).df()


def build_utilization_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    prior = con.execute("""
        SELECT c.hadm_id, COUNT(*) AS prior_admission_count, MAX(a.dischtime) AS prior_dischtime
        FROM cohort c
        JOIN admissions a
            ON a.subject_id = c.subject_id
           AND a.dischtime <= c.admittime
           AND a.hadm_id != c.hadm_id
        GROUP BY c.hadm_id
    """).df()

    cohort_admit = con.execute("SELECT hadm_id, admittime FROM cohort").df()
    features = cohort_admit.merge(prior, on="hadm_id", how="left")
    features["prior_admission_count"] = features["prior_admission_count"].fillna(0).astype(int)
    features["days_since_last_discharge"] = (
        features["admittime"] - features["prior_dischtime"]
    ).dt.days
    return features[["hadm_id", "prior_admission_count", "days_since_last_discharge"]]


def build_demographic_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    # race and insurance already come from the cohort table (extract.py pulls
    # them from admissions); only gender and age are new here.
    return con.execute("""
        SELECT c.hadm_id, p.gender, p.anchor_age
        FROM cohort c
        JOIN patients p ON p.subject_id = c.subject_id
    """).df()


def build_features(data_dir: Path, cohort_path: Path, gem_path: Path) -> pd.DataFrame:
    con = duckdb.connect()
    _register_views(con, data_dir)

    cohort = pd.read_parquet(cohort_path)
    con.register("cohort", cohort)

    feature_blocks = [
        build_comorbidity_features(con, gem_path),
        build_lab_features(con),
        build_medication_features(con),
        build_utilization_features(con),
        build_demographic_features(con),
    ]

    features = cohort
    for block in feature_blocks:
        features = features.merge(block, on="hadm_id", how="left")

    return features


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir", required=True,
        help="Path to the hosp/ folder (demo or full MIMIC-IV export)",
    )
    parser.add_argument("--cohort", default="data/interim/cohort.parquet")
    parser.add_argument("--gem", default="data/external/icd9toicd10cmgem.csv")
    parser.add_argument("--out", default="data/interim/features.parquet")
    args = parser.parse_args()

    features = build_features(Path(args.data_dir), Path(args.cohort), Path(args.gem))

    print(f"Feature table: {features.shape[0]} rows, {features.shape[1]} columns")
    null_rates = features.isna().mean().sort_values(ascending=False)
    print("Null rates (top 10):")
    print(null_rates.head(10))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(out_path)
    print(f"Saved feature table to {out_path}")
