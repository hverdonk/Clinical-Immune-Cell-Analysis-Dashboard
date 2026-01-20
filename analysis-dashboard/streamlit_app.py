from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_summary import load_summary_with_sample_metadata_from_db
from response_plot import prepare_response_plot_df, responder_boxplot_spec
from stats_utils import bh_adjust, two_sided_permutation_pvalue

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
            summary_meta = load_summary_with_sample_metadata_from_db(tmp_path)
        else:
            summary_meta = load_summary_with_sample_metadata_from_db(default_db)

    except Exception as e:
        st.error(str(e))
        st.info(
            "If you haven't created the database yet, run: python analysis-dashboard/load_cell_counts.py"
        )
        st.stop()

    st.subheader("Data Overview")
    st.dataframe(
        summary_meta,
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

    # add dropdown for users to select treatments (default to "miraclib" if present)
    treatments = (
        summary_meta["treatment"].dropna().astype(str).sort_values().unique().tolist()
    )
    default_treatments = ["miraclib"] if "miraclib" in treatments else treatments
    selected_treatments = st.multiselect(
        "Treatment",
        options=treatments,
        default=default_treatments,
    )

    # add dropdown for users to select sample types (default to "PBMC" if present)
    sample_types = (
        summary_meta["sample_type"].dropna().astype(str).sort_values().unique().tolist()
    )
    default_sample_types = ["PBMC"] if "PBMC" in sample_types else sample_types
    selected_sample_types = st.multiselect(
        "Sample type",
        options=sample_types,
        default=default_sample_types,
    )

    plot_df, populations = prepare_response_plot_df(
        summary_meta,
        selected_treatments=selected_treatments,
        selected_sample_types=selected_sample_types,
    )

    if plot_df.empty:
        st.info("No data available for the current filters (and recognized response labels).")
        return

    st.vega_lite_chart(
        plot_df,
        responder_boxplot_spec(),
        width='stretch',
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

    rows: list[dict[str, object]] = []
    for pop in populations:
        sub = plot_df[plot_df["population"].astype(str) == str(pop)]
        a = sub.loc[sub["response"] == "yes", "percentage"].to_numpy()
        b = sub.loc[sub["response"] == "no", "percentage"].to_numpy()

        if a.size < 2 or b.size < 2:
            continue

        p = two_sided_permutation_pvalue(
            a,
            b,
            n_permutations=n_permutations,
            rng=rng,
        )
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
    stats_df["p_adj_bh"] = bh_adjust(stats_df["p_value"].tolist())
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
