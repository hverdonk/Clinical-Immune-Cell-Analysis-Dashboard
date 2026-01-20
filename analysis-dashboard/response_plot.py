from __future__ import annotations

import pandas as pd


def apply_filters(
    df: pd.DataFrame,
    *,
    selected_treatments: list[str],
    selected_sample_types: list[str],
    selected_time_from_treatment_start: list[str],
) -> pd.DataFrame:
    """Filter a summary DataFrame by treatment and sample type.

    Args:
        df: Input DataFrame expected to contain `treatment` and `sample_type`
            columns.
        selected_treatments: Treatments to keep. If empty, no treatment filtering
            is applied.
        selected_sample_types: Sample types to keep. If empty, no sample type
            filtering is applied.
        selected_time_from_treatment_start: Time from treatment start to keep. If empty, no time from treatment start filtering is applied.

    Returns:
        A filtered copy of `df` containing only the selected treatments and/or
        sample types.
    """
    out = df.copy()
    if selected_treatments:
        out = out[out["treatment"].isin(selected_treatments)]
    if selected_sample_types:
        out = out[out["sample_type"].isin(selected_sample_types)]
    if selected_time_from_treatment_start:
        out = out[out["time_from_treatment_start"].isin(selected_time_from_treatment_start)]
    return out


def prepare_response_plot_df(
    summary_meta: pd.DataFrame,
    *,
    selected_treatments: list[str],
    selected_sample_types: list[str],
    selected_time_from_treatment_start: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Prepare a DataFrame for responder vs non-responder boxplots.

    Applies treatment/sample-type filters, drops rows
    with null response labels, and makes `population` an ordered
    categorical column for stable plotting.

    Args:
        summary_meta: Long-format per-sample/per-population summary DataFrame
            with sample metadata. Expected columns include: `treatment`,
            `sample_type`, `response`, and `population`.
        selected_treatments: Treatments to include (empty means include all).
        selected_sample_types: Sample types to include (empty means include all).
        selected_time_from_treatment_start: Time from treatment start to include (empty means include all).

    Returns:
        A tuple of:
        - plot_df: Filtered DataFrame containing an ordered categorical `population` column.
        - populations: The ordered list of population names used as categories.
    """
    plot_df = apply_filters(
        summary_meta,
        selected_treatments=selected_treatments,
        selected_sample_types=selected_sample_types,
        selected_time_from_treatment_start=selected_time_from_treatment_start,
    )

    plot_df = plot_df.dropna(subset=["response"])

    populations = (
        plot_df["population"].dropna().astype(str).sort_values().unique().tolist()
    )
    plot_df = plot_df.copy()
    plot_df["population"] = pd.Categorical(
        plot_df["population"], categories=populations, ordered=True
    )

    return plot_df, populations


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
        "mark": {"type": "boxplot", "extent": 1.5},
        "encoding": {
            "x": {"field": "population", "type": "nominal", "title": "Cell population"},
            "xOffset": {"field": "response"},
            "y": {
                "field": "percentage",
                "type": "quantitative",
                "title": "Relative frequency (%)",
            },
            "color": {
                "field": "response",
                "type": "nominal",
                "title": "Response",
            },
            "tooltip": [
                {"field": "sample", "type": "nominal"},
                {"field": "population", "type": "nominal"},
                {"field": "response", "type": "nominal"},
                {"field": "percentage", "type": "quantitative", "format": ".2f"},
            ],
        },
        "config": {"boxplot": {"size": 18}},
    }
