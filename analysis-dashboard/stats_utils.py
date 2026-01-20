from __future__ import annotations

import numpy as np


def two_sided_permutation_pvalue(
    a: np.ndarray,
    b: np.ndarray,
    *,
    n_permutations: int,
    rng: np.random.Generator,
) -> float:
    a = a.astype(float)
    b = b.astype(float)
    observed = float(np.abs(np.mean(a) - np.mean(b)))
    pooled = np.concatenate([a, b])
    n_a = a.size

    diffs = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        rng.shuffle(pooled)
        diffs[i] = np.abs(np.mean(pooled[:n_a]) - np.mean(pooled[n_a:]))

    return float((np.sum(diffs >= observed) + 1) / (n_permutations + 1))


def bh_adjust(p_values: list[float]) -> list[float]:
    m = len(p_values)
    order = np.argsort(p_values)
    ranked = np.array(p_values, dtype=float)[order]
    adjusted = ranked * m / (np.arange(m) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)
    out = np.empty(m, dtype=float)
    out[order] = adjusted
    return out.tolist()
