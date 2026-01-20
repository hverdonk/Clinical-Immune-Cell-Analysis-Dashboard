from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis-dashboard"))

import response_plot as rp


def test_apply_treatment_and_sample_type_filters_no_filters_returns_copy() -> None:
    """`apply_treatment_and_sample_type_filters` returns an unchanged copy when no filters are selected."""
    df = pd.DataFrame(
        {
            "treatment": ["A", "B"],
            "sample_type": ["PBMC", "TIL"],
            "other": [1, 2],
        }
    )

    out = rp.apply_treatment_and_sample_type_filters(
        df,
        selected_treatments=[],
        selected_sample_types=[],
    )

    assert out.equals(df)
    assert out is not df


def test_apply_treatment_and_sample_type_filters_filters_both_dimensions() -> None:
    """`apply_treatment_and_sample_type_filters` can filter on both treatment and sample type simultaneously."""
    df = pd.DataFrame(
        {
            "treatment": ["A", "A", "B"],
            "sample_type": ["PBMC", "TIL", "PBMC"],
            "value": [1, 2, 3],
        }
    )

    out = rp.apply_treatment_and_sample_type_filters(
        df,
        selected_treatments=["A"],
        selected_sample_types=["PBMC"],
    )

    assert len(out) == 1
    assert out.iloc[0]["treatment"] == "A"
    assert out.iloc[0]["sample_type"] == "PBMC"
    assert out.iloc[0]["value"] == 1


def test_prepare_response_plot_df_drops_null_response_and_orders_populations() -> None:
    """`prepare_response_plot_df` drops null responses and produces an ordered categorical `population` column."""
    summary_meta = pd.DataFrame(
        {
            "sample": ["S1", "S1", "S2", "S2"],
            "treatment": ["A", "A", "A", "A"],
            "sample_type": ["PBMC", "PBMC", "PBMC", "PBMC"],
            "response": ["yes", None, "no", "no"],
            "population": ["nk_cell", "b_cell", "b_cell", "cd4_t_cell"],
            "percentage": [10.0, 20.0, 30.0, 40.0],
        }
    )

    plot_df, populations = rp.prepare_response_plot_df(
        summary_meta,
        selected_treatments=["A"],
        selected_sample_types=["PBMC"],
    )

    # one row had response=None and should be dropped
    assert len(plot_df) == 3
    assert plot_df["response"].isna().sum() == 0

    # populations should be sorted unique strings
    assert populations == ["b_cell", "cd4_t_cell", "nk_cell"]

    # population column should be an ordered categorical with those categories
    assert str(plot_df["population"].dtype) == "category"
    assert list(plot_df["population"].cat.categories) == populations
    assert bool(plot_df["population"].cat.ordered) is True


def test_prepare_response_plot_df_empty_selection_means_no_filtering() -> None:
    """`prepare_response_plot_df` treats empty treatment/sample-type selections as "no filtering"."""
    summary_meta = pd.DataFrame(
        {
            "sample": ["S1", "S2"],
            "treatment": ["A", "B"],
            "sample_type": ["PBMC", "TIL"],
            "response": ["yes", "no"],
            "population": ["b_cell", "nk_cell"],
            "percentage": [10.0, 20.0],
        }
    )

    plot_df, populations = rp.prepare_response_plot_df(
        summary_meta,
        selected_treatments=[],
        selected_sample_types=[],
    )

    assert len(plot_df) == 2
    assert populations == ["b_cell", "nk_cell"]


def test_responder_boxplot_spec_uses_expected_fields() -> None:
    """`responder_boxplot_spec` encodes the expected fields for the boxplot and tooltip."""
    spec = rp.responder_boxplot_spec()

    assert spec["mark"]["type"] == "boxplot"

    enc = spec["encoding"]
    assert enc["x"]["field"] == "population"
    assert enc["xOffset"]["field"] == "response"
    assert enc["y"]["field"] == "percentage"
    assert enc["color"]["field"] == "response"

    tooltip_fields = [t["field"] for t in enc["tooltip"]]
    assert tooltip_fields == ["sample", "population", "response", "percentage"]
