from __future__ import annotations

import pandas as pd


def apply_filters(
    df: pd.DataFrame,
    *,
    selected_treatments: list[str],
    selected_sample_types: list[str],
    selected_condition: list[str],
    selected_sexes: list[str],
    selected_ages: list[int],
    selected_projects: list[str],
    selected_responses: list[str],
) -> pd.DataFrame:
    """Filter a summary DataFrame by treatment and sample type.

    Args:
        df: Input DataFrame expected to contain `treatment` and `sample_type`
            columns.
        selected_treatments: Treatments to keep. If empty, no treatment filtering
            is applied.
        selected_sample_types: Sample types to keep. If empty, no sample type
            filtering is applied.
        selected_condition: Condition (e.g., "healthy" or "melanoma") to keep. If empty, no condition filtering is applied.
        selected_sexes: Sexes to keep. If empty, no sex filtering is applied.
        selected_ages: Ages to keep. If empty, no age filtering is applied.
        selected_projects: Projects to keep. If empty, no project filtering is applied.
        selected_responses: Responses to keep. If empty, no response filtering is applied.
    Returns:
        A filtered copy of `df` containing only the selected treatments and/or
        sample types.
    """
    out = df.copy()
    if selected_treatments:
        out = out[out["treatment"].isin(selected_treatments)]
    if selected_sample_types:
        out = out[out["sample_type"].isin(selected_sample_types)]
    if selected_condition:
        out = out[out["condition"].isin(selected_condition)]
    if selected_sexes:
        out = out[out["sex"].isin(selected_sexes)]
    if selected_ages:
        out = out[out["age"].isin(selected_ages)]
    if selected_projects:
        out = out[out["project"].isin(selected_projects)]
    if selected_responses:
        out = out[out["response"].isin(selected_responses)]
    return out

def get_patient_count(
    df: pd.DataFrame,
    *,
    selected_sexes: list[str] | None = None,
    selected_ages: list[int] | None = None,
    selected_projects: list[str] | None = None,
    selected_responses: list[str] | None = None,
) -> int:
    """Get the number of unique patients in the (filtered) DataFrame.
    
    Args:
        df: DataFrame to get patient count from.
        selected_sexes: If provided, only count patients with these sexes.
        selected_ages: If provided, only count patients with these ages.
        selected_projects: If provided, only count patients in these projects.
        selected_responses: If provided, only count patients with these responses.
    
    Returns:
        Number of unique patients in the DataFrame.
    """
    filtered = df[df["time_from_treatment_start"] == 0]
    if selected_sexes:
        filtered = filtered[filtered["sex"].isin(selected_sexes)]
    if selected_ages:
        filtered = filtered[filtered["age"].isin(selected_ages)]
    if selected_projects:
        filtered = filtered[filtered["project"].isin(selected_projects)]
    if selected_responses:
        filtered = filtered[filtered["response"].isin(selected_responses)]
    return filtered["subject"].nunique()

def responder_boxplot_spec() -> dict:
    """Return the Vega-Lite spec used to render responder boxplots.

    The spec assumes the plotted data contains the columns:

    - `population`
    - `response`
    - `percentage`
    - `sample`

    Returns:
        A Vega-Lite chart specification dictionary suitable for passing to
        `st.vega_lite_chart`.
    """
    return {
        "layer": [
            {
            "mark": { "type": "boxplot", "extent": 1.5 },
            "encoding": {
                "x": { "field": "population", "type": "nominal", "title": "Cell population" },
                "xOffset": { "field": "response" },
                "y": {
                    "field": "percentage",
                    "type": "quantitative",
                    "title": "Relative frequency (%)"
                },
                "color": {
                    "field": "response",
                    "type": "nominal",
                    # "title": "Response"
                }
            }
            },
            {
            "mark": {
                "type": "point",
                "filled": True,
                "size": 60
            },
            "encoding": {
                "x": { "field": "population", "type": "nominal" },
                "xOffset": { "field": "response" },
                "y": {
                    "aggregate": "mean",
                    "field": "percentage",
                    "type": "quantitative"
                },
                # "color": {
                # "field": "response",
                # "type": "nominal"
                # },
                "color": "#000000",
                "tooltip": [
                { "aggregate": "mean", "field": "percentage", "type": "quantitative", "format": ".2f", "title": "Mean %" }
                ]
            }
            }
        ],
        "config": {
            "boxplot": { "size": 18 }
        }
    }
