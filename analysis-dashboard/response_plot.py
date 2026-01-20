from __future__ import annotations

import pandas as pd


def apply_treatment_and_sample_type_filters(
    df: pd.DataFrame,
    *,
    selected_treatments: list[str],
    selected_sample_types: list[str],
) -> pd.DataFrame:
    out = df.copy()
    if selected_treatments:
        out = out[out["treatment"].isin(selected_treatments)]
    if selected_sample_types:
        out = out[out["sample_type"].isin(selected_sample_types)]
    return out


def add_response_group_column(df: pd.DataFrame) -> pd.DataFrame:
    resp_raw = df["response"].fillna("").astype(str).str.strip().str.lower()
    out = df.assign(response_group=pd.Series(pd.NA, index=df.index, dtype="string"))

    out.loc[resp_raw.isin({"yes", "y", "responder", "responders"}), "response_group"] = (
        "Responder"
    )
    out.loc[
        resp_raw.isin(
            {
                "no",
                "n",
                "non-responder",
                "nonresponder",
                "non-responders",
                "nonresponders",
            }
        ),
        "response_group",
    ] = "Non-responder"

    return out


def prepare_response_plot_df(
    summary_meta: pd.DataFrame,
    *,
    selected_treatments: list[str],
    selected_sample_types: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    plot_df = apply_treatment_and_sample_type_filters(
        summary_meta,
        selected_treatments=selected_treatments,
        selected_sample_types=selected_sample_types,
    )

    plot_df = add_response_group_column(plot_df)
    plot_df = plot_df.dropna(subset=["response_group"])

    populations = (
        plot_df["population"].dropna().astype(str).sort_values().unique().tolist()
    )
    plot_df = plot_df.copy()
    plot_df["population"] = pd.Categorical(
        plot_df["population"], categories=populations, ordered=True
    )

    return plot_df, populations


def responder_boxplot_spec() -> dict:
    return {
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
    }
