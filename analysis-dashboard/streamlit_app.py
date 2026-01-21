from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_summary import load_summary_with_sample_metadata_from_db
from response_plot import apply_filters, get_patient_count,prepare_response_plot_df, responder_boxplot_spec
from stats_utils import analyze_all_populations

def _build_multiselect_filter(
    df: pd.DataFrame,
    column: str,
    label: str,
    default_value: str | None = None,
) -> list[str]:
    """Build a multiselect filter for a DataFrame column.
    
    Args:
        df: DataFrame containing the column to filter.
        column: Name of the column to create filter for.
        label: Label to display for the multiselect widget.
        default_value: If present in options, use as default selection.
    
    Returns:
        List of selected values from the multiselect.
    """
    options = df[column].dropna().astype(str).sort_values().unique().tolist()
    default = [default_value] if default_value and default_value in options else options
    return st.multiselect(label, options=options, default=default)


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

    st.subheader("Filters")

    # add dropdown for users to select treatments (default to "miraclib" if present)
    selected_treatments = _build_multiselect_filter(
        summary_meta, "treatment", "Treatment", default_value="miraclib"
    )

    # add dropdown for users to select sample types (default to "PBMC" if present)
    selected_sample_types = _build_multiselect_filter(
        summary_meta, "sample_type", "Sample type", default_value="PBMC"
    )

    # add sex filter with counts of number of patients in each sex for the current filters
    selected_sexes: list[str] = ["M", "F"]
    if st.session_state.sex_filter == "M":
        selected_sexes = ["M"]
    elif st.session_state.sex_filter == "F":
        selected_sexes = ["F"]

    if "sex_filter" not in st.session_state:
        st.session_state.sex_filter = None

    def _toggle_sex_filter(selected: str) -> None:
        if st.session_state.sex_filter == selected:
            st.session_state.sex_filter = None
        else:
            st.session_state.sex_filter = selected

    summary_meta_filtered = apply_filters(
        summary_meta,
        selected_treatments=selected_treatments,
        selected_sample_types=selected_sample_types,
        selected_time_from_treatment_start=[],
        selected_sexes=selected_sexes,
        selected_ages=[],
        selected_projects=[],
    )

    male_patient_count = get_patient_count(summary_meta_filtered, selected_sexes=["M"])
    female_patient_count = get_patient_count(summary_meta_filtered, selected_sexes=["F"])

    sex_filter_col_1, sex_filter_col_2 = st.columns(2)
    with sex_filter_col_1:
        st.button(
            f"Male ♂ ({male_patient_count} patients)",
            type="primary" if st.session_state.sex_filter == "M" else "secondary",
            help="Filter to males",
            use_container_width=True,
            key="sex_filter_male",
            on_click=_toggle_sex_filter,
            args=("M",),
        )

    with sex_filter_col_2:
        st.button(
            f"Female ♀ ({female_patient_count} patients)",
            type="primary" if st.session_state.sex_filter == "F" else "secondary",
            help="Filter to females",
            use_container_width=True,
            key="sex_filter_female",
            on_click=_toggle_sex_filter,
            args=("F",),
        )

    st.subheader("Data Overview")
    st.dataframe(
        summary_meta_filtered,
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

    plot_df, populations = prepare_response_plot_df(
        summary_meta_filtered,
        selected_treatments=[],
        selected_sample_types=[],
        selected_time_from_treatment_start=[],
        selected_sexes=selected_sexes,
        selected_ages=[],
        selected_projects=[],
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
