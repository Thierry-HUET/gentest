"""
profiler.py – Inférence de type et calcul de statistiques par colonne.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Types de colonnes reconnus
# ---------------------------------------------------------------------------
ColType = str  # "numeric" | "categorical" | "boolean" | "text" | "datetime" | "unknown"


def infer_column_type(series: pd.Series) -> ColType:
    """Infère le type sémantique d'une colonne."""
    s = series.dropna()
    if s.empty:
        return "unknown"

    dtype = series.dtype

    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"
    if pd.api.types.is_numeric_dtype(dtype):
        # Heuristique : peu de valeurs distinctes → catégoriel
        n_unique = s.nunique()
        if n_unique <= 2 and set(s.unique()).issubset({0, 1}):
            return "boolean"
        if n_unique / len(s) < 0.05 and n_unique <= 20:
            return "categorical"
        return "numeric"
    if pd.api.types.is_object_dtype(dtype) or isinstance(dtype, pd.StringDtype):
        n_unique = s.nunique()
        if n_unique / len(s) < 0.10 and n_unique <= 50:
            return "categorical"
        return "text"

    return "unknown"


# ---------------------------------------------------------------------------
# Statistiques par colonne
# ---------------------------------------------------------------------------
@dataclass
class ColumnProfile:
    name: str
    col_type: ColType
    null_rate: float
    n_unique: int
    # Numériques
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    q25: float | None = None
    q50: float | None = None
    q75: float | None = None
    # Catégoriel / booléen
    value_counts: dict[Any, float] = field(default_factory=dict)  # modalité → fréquence
    # Texte
    avg_length: float | None = None
    sample_values: list[str] = field(default_factory=list)
    # Datetime
    dt_min: str | None = None
    dt_max: str | None = None


def profile_dataframe(df: pd.DataFrame) -> dict[str, ColumnProfile]:
    """
    Calcule le profil statistique de chaque colonne d'un DataFrame.

    Returns
    -------
    dict[colonne → ColumnProfile]
    """
    profiles: dict[str, ColumnProfile] = {}

    for col in df.columns:
        series = df[col]
        col_type = infer_column_type(series)
        n = len(series)
        null_rate = series.isna().sum() / n if n > 0 else 0.0
        n_unique = int(series.nunique(dropna=True))

        p = ColumnProfile(
            name=col,
            col_type=col_type,
            null_rate=float(null_rate),
            n_unique=n_unique,
        )

        s = series.dropna()

        if col_type == "numeric":
            p.mean = float(s.mean())
            p.std = float(s.std())
            p.min = float(s.min())
            p.max = float(s.max())
            p.q25 = float(s.quantile(0.25))
            p.q50 = float(s.quantile(0.50))
            p.q75 = float(s.quantile(0.75))

        elif col_type in {"categorical", "boolean"}:
            vc = s.value_counts(normalize=True)
            p.value_counts = {str(k): float(v) for k, v in vc.items()}

        elif col_type == "text":
            str_series = s.astype(str)
            p.avg_length = float(str_series.str.len().mean())
            p.sample_values = str_series.sample(min(5, len(str_series)), random_state=0).tolist()

        elif col_type == "datetime":
            p.dt_min = str(s.min())
            p.dt_max = str(s.max())

        profiles[col] = p

    return profiles
