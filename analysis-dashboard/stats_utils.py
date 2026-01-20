from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests


def format_response(df: pd.DataFrame) -> pd.DataFrame:
    """Reformat a copy of the provided data frame to ensure categorical encoding by 
    cell population and patient ID.

    Args:
        df: The DataFrame containing the cell population summary data.

    Returns:
        A copy of the DataFrame with categorical encoding applied.
    """
    df = df.copy()
    df["population"] = df["population"].astype("category")
    df["patient_id"] = df["patient_id"].astype("category")
    return df

def transform_response(df: pd.DataFrame) -> pd.DataFrame:
    """Transform the response column and compute a logit-transformed proportion.
    
    Maps the response column from "no"/"yes" to 0/1 and adds a `prop_logit`
    column containing the logit transformation of the `prop` column.
    
    Args:
        df: The DataFrame containing the cell population summary data.
    
    Returns:
        A copy of the DataFrame with the response variable transformed and
        the logit-transformed proportion added.
    """
    df = df.copy()
    df["response"] = df["response"].map({"no": 0, "yes": 1})

    eps = 1e-6  # offset to avoid log(0)
    df["prop_logit"] = np.log((df["prop"] + eps) / (1 - df["prop"] + eps))
    return df

def fit_mixed_effects_model(population: str, df: pd.DataFrame) -> dict[str, float]:
    """Fit a mixed effects model to the data for a specific population.
    
    Args:
        population: The population to fit the model for.
        df: The DataFrame containing the data.
    
    Returns:
        A dictionary containing the coefficients and p-values for the model.
    """
    pop = df[df["population"] == population]

    model = smf.mixedlm(
        "prop_logit ~ response",
        pop,
        groups=pop["patient_id"]
    )

    fit = model.fit(reml=False)

    return {
        "coef_response": fit.params["response"],
        "p_value": fit.pvalues["response"]
    }

def analyze_all_populations(df: pd.DataFrame) -> pd.DataFrame:
    """Fit mixed effects models for all populations in the DataFrame.
    
    Formats and transforms the input data, then fits a mixed effects model
    for each unique population.
    
    Args:
        df: The DataFrame containing the cell population summary data with
            columns including 'population', 'patient_id', 'response', and 'prop'.
    
    Returns:
        A DataFrame with one row per population containing the model coefficients
        and p-values.
    """
    df = format_response(df)
    df = transform_response(df)
    
    # fit a mixed effects model for each population
    results = []
    for population in df["population"].cat.categories:
        result = fit_mixed_effects_model(population, df)
        result["population"] = population
        results.append(result)
    results_df = pd.DataFrame(results)

    # apply Benjamini-Hochberg multiple testing correction to p-values
    results_df["p_adj"] = multipletests(
        results_df["p_value"],
        method="fdr_bh"
    )[1]

    return results_df
