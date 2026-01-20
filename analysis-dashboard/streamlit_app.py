from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_summary import load_summary_with_sample_metadata_from_db
from response_plot import prepare_response_plot_df, responder_boxplot_spec
from stats_utils import analyze_all_populations

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

    st.subheader("Significant differences")
    st.caption(
        """Used a mixed effects model to compare responder vs non-responder relative frequencies for each immune cell population. 
        The mixed effects model accounts for non-independence of samples taken from the same patient, unlike paired t-tests, 
        Wilcoxon signed-rank tests, or similar tests that assume independence of samples. 
        Adjusted p-values using the Benjamini-Hochberg procedure."""
    )
    
    try:
        results_df = analyze_all_populations(plot_df)
        
        # Reorder columns to put population first
        cols = ["population"] + [c for c in results_df.columns if c != "population"]
        results_df = results_df[cols]
        
        # Style significant rows
        def highlight_significant(row):
            if row["p_adj"] < 0.05:
                return ["font-weight: bold; background-color: #90EE90"] * len(row)
            return [""] * len(row)
        
        styled_results = results_df.style.apply(highlight_significant, axis=1)
        st.dataframe(
            styled_results,
            hide_index=True,
            column_config={
                "coef_response": st.column_config.NumberColumn(format="%.4f"),
                "p_value": st.column_config.NumberColumn(format="%.4e"),
                "p_adj": st.column_config.NumberColumn(format="%.4e"),
            },
        )
    except Exception as e:
        st.warning(f"Could not perform statistical analysis: {e}")
    


if __name__ == "__main__":
    main()
