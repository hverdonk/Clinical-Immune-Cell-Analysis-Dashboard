from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_summary import load_summary_with_sample_metadata_from_db
from response_plot import apply_filters, get_patient_count, responder_boxplot_spec
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
    default = [default_value] if default_value and default_value in options else None
    return st.multiselect(label, options=options, default=default)

def _render_toggle_buttons(
    col1_label: str,
    col1_count: int,
    col1_value: str,
    col1_help: str,
    col2_label: str,
    col2_count: int,
    col2_value: str,
    col2_help: str,
    session_key: str,
    toggle_func: callable,
    key_prefix: str,
) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.button(
            f"{col1_label} ({col1_count} patients)",
            type="primary" if getattr(st.session_state, session_key) == col1_value else "secondary",
            help=col1_help,
            use_container_width=True,
            key=f"{key_prefix}_{col1_value}",
            on_click=toggle_func,
            args=(col1_value,),
        )
    with col2:
        st.button(
            f"{col2_label} ({col2_count} patients)",
            type="primary" if getattr(st.session_state, session_key) == col2_value else "secondary",
            help=col2_help,
            use_container_width=True,
            key=f"{key_prefix}_{col2_value}",
            on_click=toggle_func,
            args=(col2_value,),
        )


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

    # add dropdown for users to select conditions (default to "melanoma" if present)
    selected_condition = _build_multiselect_filter(
        summary_meta, "condition", "Condition", default_value="melanoma"
    )

    # add dropdown for users to select time from treatment start
    selected_time_from_treatment_start = _build_multiselect_filter(
        summary_meta, "time_from_treatment_start", "Time from treatment start"
    )

    # add sex filter with counts of number of patients in each sex for the current filters
    if "sex_filter" not in st.session_state:
        st.session_state.sex_filter = None

    sex_filter = st.session_state.get("sex_filter")

    selected_sexes: list[str] = []
    if sex_filter == "M":
        selected_sexes = ["M", "m", "Male", "male"]
    elif sex_filter == "F":
        selected_sexes = ["F", "f", "Female", "female"]

    if "response_filter" not in st.session_state:
        st.session_state.response_filter = None

    response_filter = st.session_state.get("response_filter")

    def _toggle_response_filter(selected: str) -> None:
        if st.session_state.response_filter == selected:
            st.session_state.response_filter = None
        else:
            st.session_state.response_filter = selected

    selected_responses: list[str] = []
    if response_filter == "yes":
        selected_responses = ["yes", "Yes", "YES"]
    elif response_filter == "no":
        selected_responses = ["no", "No", "NO"]

    def _toggle_sex_filter(selected: str) -> None:
        if st.session_state.sex_filter == selected:
            st.session_state.sex_filter = None
        else:
            st.session_state.sex_filter = selected

    summary_meta_base = apply_filters(
        summary_meta,
        selected_treatments=selected_treatments,
        selected_sample_types=selected_sample_types,
        selected_condition=selected_condition,
        selected_time_from_treatment_start=[],
        selected_sexes=[],
        selected_ages=[],
        selected_projects=[],
        selected_responses=[],
    )

    # Sex counts should reflect the current response selection (if any)
    male_patient_count = get_patient_count(
        summary_meta_base,
        selected_sexes=["M", "m", "Male", "male"],
        selected_responses=selected_responses,
    )
    female_patient_count = get_patient_count(
        summary_meta_base,
        selected_sexes=["F", "f", "Female", "female"],
        selected_responses=selected_responses,
    )

    # Response counts should reflect the current sex selection (if any)
    responder_patient_count = get_patient_count(
        summary_meta_base,
        selected_sexes=selected_sexes,
        selected_responses=["yes", "Yes", "YES"],
    )
    non_responder_patient_count = get_patient_count(
        summary_meta_base,
        selected_sexes=selected_sexes,
        selected_responses=["no", "No", "NO"],
    )

    summary_meta_filtered = apply_filters(
        summary_meta,
        selected_treatments=selected_treatments,
        selected_sample_types=selected_sample_types,
        selected_condition=selected_condition,
        selected_time_from_treatment_start=selected_time_from_treatment_start,
        selected_sexes=selected_sexes,
        selected_ages=[],
        selected_projects=[],
        selected_responses=selected_responses,
    )

    _render_toggle_buttons(
        col1_label="Male", 
        col1_count=male_patient_count, 
        col1_value="M", 
        col1_help="Filter to males", 
        col2_label="Female", 
        col2_count=female_patient_count, 
        col2_value="F", col2_help="Filter to females", 
        session_key="sex_filter", 
        toggle_func=_toggle_sex_filter, 
        key_prefix="sex_filter"
    )

    _render_toggle_buttons(
        col1_label="Responders",
        col1_count=responder_patient_count,
        col1_value="yes",
        col1_help="Filter to patients responding to selected drug.",
        col2_label="Non-responders",
        col2_count=non_responder_patient_count,
        col2_value="no",
        col2_help="Filter to patients not responding to selected drug.",
        session_key="response_filter",
        toggle_func=_toggle_response_filter,
        key_prefix="response_filter"
    )


    st.subheader("Data Overview")

    # Emoji grid of project counts
    if {"project", "sample", "time_from_treatment_start"}.issubset(summary_meta_filtered.columns):
        samples_per_project = (
            summary_meta_filtered.groupby("project")["sample"]
            .nunique()
            .sort_values(ascending=False)
            .reset_index(name="samples")
        )

        emoji_cycle = [
            "🧪",
            "🧫",
            "🧬",
            "🔬",
            "📊",
            "📈",
            "📉",
            "🧰",
            "🧠",
            "🩸",
            "🫁",
            "🧻",
        ]

        projects = samples_per_project["project"].astype(str).tolist()
        project_to_emoji = {
            project: emoji_cycle[i % len(emoji_cycle)] for i, project in enumerate(projects)
        }

        cols_per_row = min(6, max(1, len(projects)))
        for row_start in range(0, len(projects), cols_per_row):
            row_projects = projects[row_start : row_start + cols_per_row]
            cols = st.columns(len(row_projects))
            for col, project in zip(cols, row_projects):
                samples = int(
                    samples_per_project.loc[
                        samples_per_project["project"].astype(str) == project, "samples"
                    ].iloc[0]
                )
                with col:
                    st.markdown(
                        f"<div style='text-align: center; font-size: 42px;'>"
                        f"{project_to_emoji[project]}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div style='text-align: center; font-weight: 600;'>"
                        f"{project}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div style='text-align: center;'>"
                        f"{samples} samples"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)


    # Summary table
    st.dataframe(
        summary_meta_filtered.drop(columns=["prop"]),
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

    plot_df = summary_meta_filtered.dropna(subset=["response"])

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
