from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd


def load_summary_with_sample_metadata_from_db(db_path: Path) -> pd.DataFrame:
    """Load summary data with sample metadata from a sqlite database.
    
    Args:
        db_path: Path to the database file.
    
    Returns:
        A DataFrame containing the summary data with sample metadata.
    """
    if not db_path.exists():
        raise FileNotFoundError(str(db_path))

    conn = sqlite3.connect(db_path)
    try:
        query = """
            SELECT
                p.name AS project,
                sub.subject_code AS subject,
                sub.condition AS condition,
                sub.age AS age,
                sub.sex AS sex,
                s.sample_code AS sample,
                s.sample_type AS sample_type,
                s.time_from_treatment_start AS time_from_treatment_start,
                s.treatment AS treatment,
                s.response AS response,
                totals.total_count AS total_count,
                cp.name AS population,
                scc.count AS count,
                (scc.count * 1.0 / totals.total_count) AS prop,
                (scc.count * 100.0 / totals.total_count) AS percentage
            FROM sample_cell_count scc
            JOIN sample s ON s.id = scc.sample_id
            JOIN subject sub ON sub.id = s.subject_id
            JOIN project p ON p.id = sub.project_id
            JOIN cell_population cp ON cp.id = scc.population_id
            JOIN (
                SELECT
                    sample_id,
                    SUM(count) AS total_count
                FROM sample_cell_count
                GROUP BY sample_id
            ) totals ON totals.sample_id = scc.sample_id
            ORDER BY s.sample_code, cp.name
        """

        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    required = {
        "project",
        "subject",
        "condition",
        "age",
        "sex",
        "sample",
        "sample_type",
        "time_from_treatment_start",
        "treatment",
        "response",
        "total_count",
        "population",
        "count",
        "prop",
        "percentage",
    }
    missing = required.difference(set(df.columns))
    if missing:
        raise RuntimeError(f"DB query missing expected columns: {sorted(missing)}")

    df["total_count"] = pd.to_numeric(df["total_count"], errors="raise").astype(int)
    df["count"] = pd.to_numeric(df["count"], errors="raise").astype(int)
    df["percentage"] = pd.to_numeric(df["percentage"], errors="raise")
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["time_from_treatment_start"] = pd.to_numeric(
        df["time_from_treatment_start"], errors="coerce"
    )

    return df[
        [
            "project",
            "subject",
            "condition",
            "age",
            "sex",
            "sample",
            "sample_type",
            "time_from_treatment_start",
            "treatment",
            "response",
            "total_count",
            "population",
            "count",
            "prop",
            "percentage",
        ]
    ]
