from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis-dashboard"))

import stats_utils as su


def test_format_response_casts_population_and_patient_to_category_and_returns_copy() -> None:
    """`format_response` casts `population` and `patient_id` to categorical types and returns a copy."""
    df = pd.DataFrame(
        {
            "population": ["b_cell", "nk_cell"],
            "patient_id": ["P1", "P2"],
            "response": ["yes", "no"],
            "prop": [0.1, 0.2],
        }
    )

    out = su.format_response(df)

    assert out is not df
    assert str(out["population"].dtype) == "category"
    assert str(out["patient_id"].dtype) == "category"


def test_transform_response_maps_yes_no_and_adds_prop_logit() -> None:
    """`transform_response` maps "no"/"yes" to 0/1 and adds a numerically stable logit column."""
    df = pd.DataFrame(
        {
            "population": ["b_cell", "b_cell"],
            "patient_id": ["P1", "P2"],
            "response": ["no", "yes"],
            "prop": [0.25, 0.75],
        }
    )

    out = su.transform_response(df)

    assert out is not df
    assert out["response"].tolist() == [0, 1]

    eps = 1e-6
    expected = np.log((df["prop"] + eps) / (1 - df["prop"] + eps))
    assert np.allclose(out["prop_logit"].to_numpy(), expected.to_numpy())


def test_transform_response_handles_prop_near_bounds_without_inf() -> None:
    """`transform_response` avoids infinities when `prop` is at the [0, 1] boundaries."""
    df = pd.DataFrame(
        {
            "population": ["b_cell", "b_cell"],
            "patient_id": ["P1", "P2"],
            "response": ["no", "yes"],
            "prop": [0.0, 1.0],
        }
    )

    out = su.transform_response(df)

    vals = out["prop_logit"].to_numpy()
    assert np.isfinite(vals).all()


def test_fit_mixed_effects_model_returns_expected_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """`fit_mixed_effects_model` returns the response coefficient and p-value (mocked statsmodels fit)."""
    df = pd.DataFrame(
        {
            "population": ["b_cell", "b_cell", "nk_cell"],
            "patient_id": ["P1", "P2", "P1"],
            "response": [0, 1, 0],
            "prop_logit": [0.1, 0.2, 0.3],
        }
    )

    class _FakeFit:
        params = {"response": 1.23}
        pvalues = {"response": 0.045}

    class _FakeModel:
        def fit(self, reml: bool = False):
            assert reml is False
            return _FakeFit()

    def _fake_mixedlm(formula, data, groups):
        assert formula == "prop_logit ~ response"
        assert (data["population"] == "b_cell").all()
        # ensure groups passed is the population-filtered patient_id series
        assert groups.equals(data["patient_id"])
        return _FakeModel()

    monkeypatch.setattr(su.smf, "mixedlm", _fake_mixedlm)

    out = su.fit_mixed_effects_model("b_cell", df)

    assert out == {"coef_response": 1.23, "p_value": 0.045}


def test_analyze_all_populations_includes_all_categories_and_adjusts_pvalues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`analyze_all_populations` runs per-population fits and computes FDR-adjusted p-values."""
    df = pd.DataFrame(
        {
            "population": ["b_cell", "nk_cell", "b_cell", "nk_cell"],
            "patient_id": ["P1", "P1", "P2", "P2"],
            "response": ["no", "yes", "yes", "no"],
            "prop": [0.2, 0.3, 0.4, 0.5],
        }
    )

    def _fake_fit(population: str, _df: pd.DataFrame) -> dict[str, float]:
        if population == "b_cell":
            return {"coef_response": 0.5, "p_value": 0.01}
        if population == "nk_cell":
            return {"coef_response": -0.25, "p_value": 0.04}
        raise AssertionError(f"Unexpected population: {population}")

    monkeypatch.setattr(su, "fit_mixed_effects_model", _fake_fit)

    out = su.analyze_all_populations(df)

    assert set(out.columns) == {"population", "coef_response", "p_value", "p_adj"}
    assert set(out["population"].tolist()) == {"b_cell", "nk_cell"}

    # fdr_bh adjusted p-values should be >= raw p-values and within [0, 1]
    assert (out["p_adj"] >= out["p_value"]).all()
    assert ((out["p_adj"] >= 0) & (out["p_adj"] <= 1)).all()
