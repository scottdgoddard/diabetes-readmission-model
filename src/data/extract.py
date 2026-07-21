"""
src/data/extract.py

Extracts the diabetic 30-day-readmission cohort from a local MIMIC-IV
(Demo or full) hosp-module export, using DuckDB to query the CSVs directly
without a separate database load step.

Usage:
    python src/data/extract.py --data-dir data/raw/mimic-iv-demo/hosp --out data/interim/cohort.parquet

Swapping from the demo dataset to the full credentialed MIMIC-IV data later
is just a matter of pointing --data-dir at the full hosp/ export -- the
query logic below is unchanged. This is the DuckDB-adapted version of
sql/cohort_definition.sql (which was written against BigQuery syntax).
"""

import argparse
from pathlib import Path

import duckdb


COHORT_QUERY = """
WITH diabetic_admissions AS (
    SELECT DISTINCT subject_id, hadm_id
    FROM diagnoses_icd
    WHERE
        (icd_version = 9 AND icd_code LIKE '250%')
        OR (icd_version = 10 AND substr(icd_code, 1, 3) BETWEEN 'E08' AND 'E13')
),

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
    FROM admissions a
    INNER JOIN diabetic_admissions da
        ON a.subject_id = da.subject_id AND a.hadm_id = da.hadm_id
),

-- Exclude admissions ending in death or hospice discharge -- a patient who
-- died cannot be "readmitted." Run the check_discharge_locations() helper
-- below first to confirm these string patterns match your actual data.
eligible_admissions AS (
    SELECT *
    FROM admissions_base
    WHERE
        deathtime IS NULL
        AND hospital_expire_flag = 0
        AND upper(coalesce(discharge_location, '')) NOT LIKE '%HOSPICE%'
        AND upper(coalesce(discharge_location, '')) NOT LIKE '%DIED%'
),

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
    date_diff('day', dischtime, next_admittime) AS days_to_next_admission,
    CASE
        WHEN next_admittime IS NOT NULL
         AND date_diff('day', dischtime, next_admittime) <= 30
        THEN 1 ELSE 0
    END AS readmitted_30d
FROM with_next_admission
ORDER BY subject_id, admittime
"""


def _register_views(con: duckdb.DuckDBPyConnection, data_dir: Path) -> None:
    con.execute(f"""
        CREATE OR REPLACE VIEW admissions AS
        SELECT * FROM read_csv_auto('{data_dir}/admissions.csv.gz')
    """)
    con.execute(f"""
        CREATE OR REPLACE VIEW diagnoses_icd AS
        SELECT * FROM read_csv_auto('{data_dir}/diagnoses_icd.csv.gz')
    """)


def check_discharge_locations(data_dir: Path) -> None:
    """Print the actual discharge_location values so the hospice/death
    exclusion filter above can be verified against real data before
    trusting it."""
    con = duckdb.connect()
    _register_views(con, data_dir)
    print(con.execute("""
        SELECT discharge_location, COUNT(*) AS n
        FROM admissions
        GROUP BY discharge_location
        ORDER BY n DESC
    """).df())


def build_cohort(data_dir: Path):
    con = duckdb.connect()
    _register_views(con, data_dir)
    return con.execute(COHORT_QUERY).df()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir", required=True,
        help="Path to the hosp/ folder (demo or full MIMIC-IV export)",
    )
    parser.add_argument("--out", default="data/interim/cohort.parquet")
    parser.add_argument(
        "--check-discharge-locations", action="store_true",
        help="Print distinct discharge_location values instead of building the cohort",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    if args.check_discharge_locations:
        check_discharge_locations(data_dir)
    else:
        cohort = build_cohort(data_dir)
        print(f"Cohort size: {len(cohort)} admissions, {cohort['subject_id'].nunique()} patients")
        print(f"Readmitted-within-30-days rate: {cohort['readmitted_30d'].mean():.3f}")

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cohort.to_parquet(out_path)
        print(f"Saved cohort to {out_path}")
