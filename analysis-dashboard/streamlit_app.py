from __future__ import annotations

from pathlib import Path
import sys
import sqlite3

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

import load_cell_counts as lcc


def load_summary_from_db(db_path: Path) -> pd.DataFrame:
    """Load a per-sample, per-population summary table from the SQLite database.

    The returned table is in long format with one row per `(sample, population)`
    pair and includes the total cell count per sample as well as population
    counts and percentages.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A DataFrame with columns: `sample`, `total_count`, `population`, `count`,
        and `percentage`.

    Raises:
        FileNotFoundError: If `db_path` does not exist.
        RuntimeError: If the SQL query does not return the expected columns.
    """
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


def load_summary_with_sample_metadata_from_db(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(str(db_path))

    conn = sqlite3.connect(db_path)
    try:
        query = """
            SELECT
                s.sample_code AS sample,
                s.sample_type AS sample_type,
                s.treatment AS treatment,
                s.response AS response,
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

    required = {
        "sample",
        "sample_type",
        "treatment",
        "response",
        "total_count",
        "population",
        "count",
        "percentage",
    }
    missing = required.difference(set(df.columns))
    if missing:
        raise RuntimeError(f"DB query missing expected columns: {sorted(missing)}")

    df["total_count"] = pd.to_numeric(df["total_count"], errors="raise").astype(int)
    df["count"] = pd.to_numeric(df["count"], errors="raise").astype(int)
    df["percentage"] = pd.to_numeric(df["percentage"], errors="raise")

    return df[
        [
            "sample",
            "sample_type",
            "treatment",
            "response",
            "total_count",
            "population",
            "count",
            "percentage",
        ]
    ]



def main() -> None:
    """Run the Streamlit application UI.

    The UI loads summary data from a default database or from a user-uploaded
    SQLite file and displays it as an interactive table.

    Args:
        None.

    Returns:
        None.
    """
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
            summary_meta = load_summary_with_sample_metadata_from_db(tmp_path)
        else:
            summary = load_summary_from_db(default_db)
            summary_meta = load_summary_with_sample_metadata_from_db(default_db)

    except Exception as e:
        st.error(str(e))
        st.info(
            "If you haven't created the database yet, run: python analysis-dashboard/load_cell_counts.py"
        )
        st.stop()

    st.subheader("Data Overview")
    st.dataframe(
        summary,
        width='stretch',
        hide_index=True,
        column_config={
            "percentage": st.column_config.NumberColumn(format="%.2f")
        },
    )

    st.subheader("Responders vs Non-responders")
    st.caption(
        "Boxplots show per-sample relative frequencies (%) for each immune cell population, split by response."
    )

    treatments = (
        summary_meta["treatment"].dropna().astype(str).sort_values().unique().tolist()
    )
    default_treatments = ["miraclib"] if "miraclib" in treatments else treatments
    selected_treatments = st.multiselect(
        "Treatment",
        options=treatments,
        default=default_treatments,
    )

    sample_types = (
        summary_meta["sample_type"].dropna().astype(str).sort_values().unique().tolist()
    )
    default_sample_types = ["PBMC"] if "PBMC" in sample_types else sample_types
    selected_sample_types = st.multiselect(
        "Sample type",
        options=sample_types,
        default=default_sample_types,
    )

    plot_df = summary_meta.copy()
    if selected_treatments:
        plot_df = plot_df[plot_df["treatment"].isin(selected_treatments)]
    if selected_sample_types:
        plot_df = plot_df[plot_df["sample_type"].isin(selected_sample_types)]

    resp_raw = plot_df["response"].fillna("").astype(str).str.strip().str.lower()
    plot_df = plot_df.assign(
        response_group=pd.Series(pd.NA, index=plot_df.index, dtype="string")
    )
    plot_df.loc[resp_raw.isin({"yes", "y", "responder", "responders"}), "response_group"] = (
        "Responder"
    )
    plot_df.loc[
        resp_raw.isin({"no", "n", "non-responder", "nonresponder", "non-responders", "nonresponders"}),
        "response_group",
    ] = "Non-responder"

    plot_df = plot_df.dropna(subset=["response_group"])

    if plot_df.empty:
        st.info("No data available for the current filters (and recognized response labels).")
        return

    populations = (
        plot_df["population"].dropna().astype(str).sort_values().unique().tolist()
    )
    plot_df["population"] = pd.Categorical(plot_df["population"], categories=populations, ordered=True)

    st.vega_lite_chart(
        plot_df,
        {
            "mark": {"type": "boxplot", "extent": 1.5},
            "encoding": {
                "x": {"field": "population", "type": "nominal", "title": "Cell population"},
                "xOffset": {"field": "response_group"},
                "y": {
                    "field": "percentage",
                    "type": "quantitative",
                    "title": "Relative frequency (%)",
                },
                "color": {
                    "field": "response_group",
                    "type": "nominal",
                    "title": "Response",
                },
                "tooltip": [
                    {"field": "sample", "type": "nominal"},
                    {"field": "population", "type": "nominal"},
                    {"field": "response_group", "type": "nominal"},
                    {"field": "percentage", "type": "quantitative", "format": ".2f"},
                ],
            },
            "config": {"boxplot": {"size": 18}},
        },
        use_container_width=True,
    )

    st.markdown("---")
    st.subheader("Significant differences")

    rng = np.random.default_rng(0)
    n_permutations = st.slider(
        "Permutation test iterations",
        min_value=200,
        max_value=5000,
        value=2000,
        step=200,
        help="Higher values give more stable p-values but take longer.",
    )

    def _two_sided_permutation_pvalue(a: np.ndarray, b: np.ndarray) -> float:
        a = a.astype(float)
        b = b.astype(float)
        observed = float(np.abs(np.mean(a) - np.mean(b)))
        pooled = np.concatenate([a, b])
        n_a = a.size

        diffs = np.empty(n_permutations, dtype=float)
        for i in range(n_permutations):
            rng.shuffle(pooled)
            diffs[i] = np.abs(np.mean(pooled[:n_a]) - np.mean(pooled[n_a:]))

        return float((np.sum(diffs >= observed) + 1) / (n_permutations + 1))

    def _bh_adjust(p_values: list[float]) -> list[float]:
        m = len(p_values)
        order = np.argsort(p_values)
        ranked = np.array(p_values, dtype=float)[order]
        adjusted = ranked * m / (np.arange(m) + 1)
        adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
        adjusted = np.clip(adjusted, 0.0, 1.0)
        out = np.empty(m, dtype=float)
        out[order] = adjusted
        return out.tolist()

    rows: list[dict[str, object]] = []
    for pop in populations:
        sub = plot_df[plot_df["population"].astype(str) == str(pop)]
        a = sub.loc[sub["response_group"] == "Responder", "percentage"].to_numpy()
        b = sub.loc[sub["response_group"] == "Non-responder", "percentage"].to_numpy()

        if a.size < 2 or b.size < 2:
            continue

        p = _two_sided_permutation_pvalue(a, b)
        rows.append(
            {
                "population": str(pop),
                "n_responders": int(a.size),
                "n_non_responders": int(b.size),
                "mean_resp": float(np.mean(a)),
                "mean_non_resp": float(np.mean(b)),
                "median_resp": float(np.median(a)),
                "median_non_resp": float(np.median(b)),
                "delta_mean": float(np.mean(a) - np.mean(b)),
                "delta_median": float(np.median(a) - np.median(b)),
                "p_value": float(p),
            }
        )

    if not rows:
        st.info(
            "Not enough samples per group to run statistics (need at least 2 responders and 2 non-responders per population)."
        )
        return

    stats_df = pd.DataFrame(rows)
    stats_df["p_adj_bh"] = _bh_adjust(stats_df["p_value"].tolist())
    stats_df = stats_df.sort_values(["p_adj_bh", "p_value", "population"], ascending=[True, True, True])

    st.dataframe(
        stats_df,
        width="stretch",
        hide_index=True,
        column_config={
            "mean_resp": st.column_config.NumberColumn(format="%.3f"),
            "mean_non_resp": st.column_config.NumberColumn(format="%.3f"),
            "median_resp": st.column_config.NumberColumn(format="%.3f"),
            "median_non_resp": st.column_config.NumberColumn(format="%.3f"),
            "delta_mean": st.column_config.NumberColumn(format="%.3f"),
            "delta_median": st.column_config.NumberColumn(format="%.3f"),
            "p_value": st.column_config.NumberColumn(format="%.4f"),
            "p_adj_bh": st.column_config.NumberColumn(format="%.4f"),
        },
    )

    sig = stats_df[stats_df["p_adj_bh"] <= 0.05]
    if sig.empty:
        st.info("No populations are significant at BH-adjusted p <= 0.05 with the current filters.")
    else:
        st.success(
            "Significant populations (BH-adjusted p <= 0.05): "
            + ", ".join(sig["population"].tolist())
        )


if __name__ == "__main__":
    main()
