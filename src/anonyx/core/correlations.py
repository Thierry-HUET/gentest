"""
correlations.py – Détection des paires de colonnes sensibles.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from anonyx.core.profiler import ColumnProfile

SENSITIVITY_THRESHOLD = 0.7

# Filtre les warnings scipy au niveau du module — persistant pour toute la session
warnings.filterwarnings("ignore", category=stats.ConstantInputWarning)
warnings.filterwarnings("ignore", message=".*constant.*", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*invalid value encountered in divide.*")


@dataclass
class CorrelationPair:
    col_a: str
    col_b: str
    method: str
    coefficient: float
    sensitive: bool


def _is_constant(series: pd.Series) -> bool:
    """Retourne True si la série est constante (std == 0 ou un seul unique)."""
    s = series.dropna()
    if len(s) < 2:
        return True
    return float(np.std(s.values, ddof=0)) == 0.0


def detect_sensitive_pairs(
    df: pd.DataFrame,
    profiles: dict[str, ColumnProfile],
    threshold: float = SENSITIVITY_THRESHOLD,
) -> list[CorrelationPair]:
    numeric_cols = [
        col for col, p in profiles.items()
        if p.col_type == "numeric" and not _is_constant(df[col])
    ]

    pairs: list[CorrelationPair] = []

    for i in range(len(numeric_cols)):
        for j in range(i + 1, len(numeric_cols)):
            ca, cb = numeric_cols[i], numeric_cols[j]
            sub = df[[ca, cb]].dropna()

            if len(sub) < 10:
                continue
            if _is_constant(sub[ca]) or _is_constant(sub[cb]):
                continue

            try:
                r_pearson,  _ = stats.pearsonr(sub[ca],  sub[cb])
                r_spearman, _ = stats.spearmanr(sub[ca], sub[cb])
            except Exception:
                continue

            if np.isnan(r_pearson) or np.isnan(r_spearman):
                continue

            if abs(abs(r_pearson) - abs(r_spearman)) > 0.15:
                coef, method = float(r_spearman), "spearman"
            else:
                coef, method = float(r_pearson),  "pearson"

            pairs.append(CorrelationPair(
                col_a=ca, col_b=cb, method=method,
                coefficient=coef, sensitive=abs(coef) > threshold,
            ))

    return pairs


def sensitive_only(pairs: list[CorrelationPair]) -> list[CorrelationPair]:
    return [p for p in pairs if p.sensitive]
