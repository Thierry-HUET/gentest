"""
correlations.py – Détection des paires de colonnes sensibles.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from anonyx.core.profiler import ColumnProfile

SENSITIVITY_THRESHOLD = 0.7


@dataclass
class CorrelationPair:
    col_a: str
    col_b: str
    method: str
    coefficient: float
    sensitive: bool


def detect_sensitive_pairs(
    df: pd.DataFrame,
    profiles: dict[str, ColumnProfile],
    threshold: float = SENSITIVITY_THRESHOLD,
) -> list[CorrelationPair]:
    numeric_cols = [col for col, p in profiles.items() if p.col_type == "numeric"]
    pairs: list[CorrelationPair] = []
    n = len(numeric_cols)

    for i in range(n):
        for j in range(i + 1, n):
            ca, cb = numeric_cols[i], numeric_cols[j]
            sub = df[[ca, cb]].dropna()
            if len(sub) < 10:
                continue
            r_pearson, _  = stats.pearsonr(sub[ca], sub[cb])
            r_spearman, _ = stats.spearmanr(sub[ca], sub[cb])
            if abs(abs(r_pearson) - abs(r_spearman)) > 0.15:
                coef, method = r_spearman, "spearman"
            else:
                coef, method = r_pearson, "pearson"
            pairs.append(CorrelationPair(
                col_a=ca, col_b=cb, method=method,
                coefficient=float(coef), sensitive=abs(coef) > threshold,
            ))
    return pairs


def sensitive_only(pairs: list[CorrelationPair]) -> list[CorrelationPair]:
    return [p for p in pairs if p.sensitive]
