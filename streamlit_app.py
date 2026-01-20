from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st

import load_cell_counts as lcc


def load_summary_from_db(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(str(db_path))

    conn = sqlite3.connect(db_path)
    try:
        query = """
            SELECT
                s.sample_code AS sample,
                totals.total_count AS total_count,
                cp.name AS population,
                scc.count AS count,
                (scc.count * 100.0 / totals.total_count) AS percentage
            FROM sample_cell_count scc
            JOIN sample s ON s.id = scc.sample_id
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

    required = {"sample", "total_count", "population", "count", "percentage"}
    missing = required.difference(set(df.columns))
    if missing:
        raise RuntimeError(f"DB query missing expected columns: {sorted(missing)}")

    df["total_count"] = pd.to_numeric(df["total_count"], errors="raise").astype(int)
    df["count"] = pd.to_numeric(df["count"], errors="raise").astype(int)
    df["percentage"] = pd.to_numeric(df["percentage"], errors="raise")

    return df[["sample", "total_count", "population", "count", "percentage"]]


def main() -> None:
    st.set_page_config(page_title="Immune Cell Frequencies", layout="wide")
    st.title("Immune Cell Population Relative Frequencies")

    base = Path(__file__).resolve().parent
    default_db = base / "cell_counts.sqlite"

    st.sidebar.header("Data")
    uploaded = st.sidebar.file_uploader("Upload cell_counts.sqlite", type=["sqlite", "db"])

    try:
        if uploaded is not None:
            tmp_path = base / ".uploaded_cell_counts.sqlite"
            tmp_path.write_bytes(uploaded.getvalue())
            summary = load_summary_from_db(tmp_path)
        else:
            summary = load_summary_from_db(default_db)

    except Exception as e:
        st.error(str(e))
        st.info("If you haven't created the database yet, run: python load_cell_counts.py")
        st.stop()

    st.subheader("Summary Table")
    st.dataframe(
        summary,
        width='stretch',
        hide_index=True,
        column_config={
            "percentage": st.column_config.NumberColumn(format="%.2f")
        },
    )


if __name__ == "__main__":
    main()
