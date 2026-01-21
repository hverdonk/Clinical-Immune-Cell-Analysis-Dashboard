from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis-dashboard"))

import response_plot as rp


def test_apply_filters_no_filters_returns_copy() -> None:
    """`apply_filters` returns an unchanged copy when no filters are selected."""
    df = pd.DataFrame(
        {
            "treatment": ["A", "B"],
            "sample_type": ["PBMC", "TIL"],
            "time_from_treatment_start": [0, 7],
            "condition": ["healthy", "melanoma"],
            "sex": ["F", "M"],
            "age": [34, 45],
            "project": ["P1", "P2"],
            "response": ["yes", "no"],
            "other": [1, 2],
        }
    )

    out = rp.apply_filters(
        df,
        selected_treatments=[],
        selected_sample_types=[],
        selected_condition=[],
        selected_sexes=[],
        selected_ages=[],
        selected_projects=[],
        selected_responses=[],
    )

    assert out.equals(df)
    assert out is not df


def test_apply_filters_filters_multiple_dimensions() -> None:
    """`apply_filters` can filter on multiple dimensions simultaneously."""
    df = pd.DataFrame(
        {
            "treatment": ["A", "A", "B", "B"],
            "sample_type": ["PBMC", "TIL", "PBMC", "PBMC"],
            "time_from_treatment_start": [0, 0, 0, 7],
            "condition": ["melanoma", "melanoma", "healthy", "melanoma"],
            "sex": ["F", "F", "M", "F"],
            "age": [34, 34, 45, 34],
            "project": ["P1", "P1", "P2", "P1"],
            "response": ["R", "NR", "R", "R"],
            "value": [1, 2, 3, 4],
        }
    )

    out = rp.apply_filters(
        df,
        selected_treatments=["A"],
        selected_sample_types=["PBMC"],
        selected_condition=["melanoma"],
        selected_sexes=[],
        selected_ages=[],
        selected_projects=[],
        selected_responses=["R"],
    )

    assert len(out) == 1 
    assert out.iloc[0]["treatment"] == "A"
    assert out.iloc[0]["sample_type"] == "PBMC"
    assert out.iloc[0]["condition"] == "melanoma"
    assert out.iloc[0]["response"] == "R"
    assert out.iloc[0]["value"] == 1


def test_apply_filters_filters_condition() -> None:
    """`apply_filters` can filter on condition."""
    df = pd.DataFrame(
        {
            "treatment": ["A", "A", "A", "A"],
            "sample_type": ["PBMC", "PBMC", "PBMC", "PBMC"],
            "time_from_treatment_start": [0, 7, 14, 0],
            "condition": ["healthy", "melanoma", "healthy", "melanoma"],
            "sex": ["F", "F", "F", "F"],
            "age": [34, 34, 34, 34],
            "project": ["P1", "P1", "P1", "P1"],
            "response": ["R", "R", "NR", "NR"],
            "value": [1, 2, 3, 4],
        }
    )

    out = rp.apply_filters(
        df,
        selected_treatments=[],
        selected_sample_types=[],
        selected_condition=["healthy"],
        selected_sexes=[],
        selected_ages=[],
        selected_projects=[],
        selected_responses=[],
    )

    assert out["condition"].unique().tolist() == ["healthy"]
    assert out["value"].tolist() == [1, 3]


def test_apply_filters_filters_sex_age_and_project() -> None:
    """`apply_filters` filters on selected sexes, ages, and projects."""
    df = pd.DataFrame(
        {
            "treatment": ["A", "A", "A", "A"],
            "sample_type": ["PBMC", "PBMC", "PBMC", "PBMC"],
            "time_from_treatment_start": [0, 0, 0, 0],
            "condition": ["melanoma", "melanoma", "healthy", "healthy"],
            "sex": ["F", "M", "F", "M"],
            "age": [34, 34, 50, 50],
            "project": ["P1", "P1", "P2", "P2"],
            "response": ["R", "R", "NR", "NR"],
            "value": [1, 2, 3, 4],
        }
    )

    out = rp.apply_filters(
        df,
        selected_treatments=[],
        selected_sample_types=[],
        selected_condition=[],
        selected_sexes=["F"],
        selected_ages=[34],
        selected_projects=["P1"],
        selected_responses=[],
    )

    assert len(out) == 1
    assert out.iloc[0]["sex"] == "F"
    assert out.iloc[0]["age"] == 34
    assert out.iloc[0]["project"] == "P1"
    assert out.iloc[0]["value"] == 1


def test_apply_filters_filters_response_only() -> None:
    """`apply_filters` can filter by response alone."""
    df = pd.DataFrame(
        {
            "treatment": ["A", "A", "A"],
            "sample_type": ["PBMC", "PBMC", "PBMC"],
            "time_from_treatment_start": [0, 0, 0],
            "condition": ["melanoma", "melanoma", "melanoma"],
            "sex": ["F", "M", "F"],
            "age": [34, 45, 34],
            "project": ["P1", "P1", "P2"],
            "response": ["R", "NR", "R"],
            "value": [1, 2, 3],
        }
    )

    out = rp.apply_filters(
        df,
        selected_treatments=[],
        selected_sample_types=[],
        selected_condition=[],
        selected_sexes=[],
        selected_ages=[],
        selected_projects=[],
        selected_responses=["R"],
    )

    assert out["response"].unique().tolist() == ["R"]
    assert out["value"].tolist() == [1, 3]


def test_responder_boxplot_spec_uses_expected_fields() -> None:
    """`responder_boxplot_spec` encodes the expected fields for the boxplot and mean overlay."""
    spec = rp.responder_boxplot_spec()

    assert "layer" in spec
    assert len(spec["layer"]) == 2

    box = spec["layer"][0]
    assert box["mark"]["type"] == "boxplot"
    box_enc = box["encoding"]
    assert box_enc["x"]["field"] == "population"
    assert box_enc["xOffset"]["field"] == "response"
    assert box_enc["y"]["field"] == "percentage"
    assert box_enc["color"]["field"] == "response"

    mean = spec["layer"][1]
    assert mean["mark"]["type"] == "point"
    mean_enc = mean["encoding"]
    assert mean_enc["x"]["field"] == "population"
    assert mean_enc["xOffset"]["field"] == "response"
    assert mean_enc["y"]["aggregate"] == "mean"
    assert mean_enc["y"]["field"] == "percentage"
    assert mean_enc["color"] == "#000000"

    tooltip = mean_enc["tooltip"]
    assert len(tooltip) == 1
    assert tooltip[0]["aggregate"] == "mean"
    assert tooltip[0]["field"] == "percentage"


def test_get_patient_count_counts_subjects_at_baseline_only() -> None:
    """`get_patient_count` counts unique subjects at baseline (time_from_treatment_start == 0)."""
    df = pd.DataFrame(
        {
            "subject": ["S1", "S1", "S2", "S2"],
            "time_from_treatment_start": [0, 7, 0, 7],
            "sex": ["F", "F", "M", "M"],
            "age": [34, 34, 45, 45],
            "project": ["P1", "P1", "P2", "P2"],
            "response": ["R", "R", "NR", "NR"],
        }
    )

    assert rp.get_patient_count(df) == 2


def test_get_patient_count_applies_optional_filters() -> None:
    """`get_patient_count` can filter by sex, age, project, and response."""
    df = pd.DataFrame(
        {
            "subject": ["S1", "S1", "S2", "S3", "S3"],
            "time_from_treatment_start": [0, 7, 0, 0, 7],
            "sex": ["F", "F", "M", "F", "F"],
            "age": [34, 34, 45, 34, 34],
            "project": ["P1", "P1", "P2", "P1", "P1"],
            "response": ["R", "R", "NR", "NR", "NR"],
        }
    )

    assert (
        rp.get_patient_count(
            df,
            selected_sexes=["F"],
            selected_ages=[34],
            selected_projects=["P1"],
            selected_responses=["R"],
        )
        == 1
    )
