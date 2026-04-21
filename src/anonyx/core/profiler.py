"""
profiler.py – Inférence de type et calcul de statistiques par colonne.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


ColType = str  # "numeric" | "categorical" | "boolean" | "text" | "datetime" | "unknown"

_IDENTIFIER_KEYWORDS = {
    "id", "code", "key", "num", "ref", "mmsi", "uuid",
    "hash", "ident", "number", "no", "nr", "index",
}

_YEAR_KEYWORDS = {
    "annee", "année", "year", "an_", "_an", "yr",
    "construction", "fabrication", "naissance", "birth",
}

_YEAR_MIN, _YEAR_MAX = 1000, 2100


def _is_likely_identifier(series: pd.Series, col_name: str) -> bool:
    s = series.dropna()
    if s.empty:
        return False
    name_lower = col_name.lower()
    if any(kw in name_lower for kw in _IDENTIFIER_KEYWORDS):
        return True
    if pd.api.types.is_integer_dtype(series.dtype):
        if s.nunique() / len(s) > 0.80:
            return True
    return False


def _is_likely_year(series: pd.Series, col_name: str) -> bool:
    s = series.dropna()
    if s.empty:
        return False
    try:
        s_num = pd.to_numeric(s, errors="coerce").dropna()
        if s_num.empty:
            return False
        if not (_YEAR_MIN <= s_num.min() and s_num.max() <= _YEAR_MAX):
            return False
        if not (s_num == s_num.apply(lambda x: int(x))).all():
            return False
    except Exception:
        return False
    name_lower = col_name.lower()
    if any(kw in name_lower for kw in _YEAR_KEYWORDS):
        return True
    if s_num.nunique() <= 200:
        return True
    return False


def _is_integer_valued(series: pd.Series) -> bool:
    """
    Retourne True si la série numérique ne contient que des valeurs entières
    (dtype int* ou float dont tous les éléments sont sans partie décimale).
    """
    s = series.dropna()
    if s.empty:
        return False
    if pd.api.types.is_integer_dtype(series.dtype):
        return True
    if pd.api.types.is_float_dtype(series.dtype):
        try:
            return bool((s == s.apply(lambda x: float(int(x)))).all())
        except (ValueError, OverflowError):
            return False
    return False


def _to_str_clean(series: pd.Series) -> pd.Series:
    if pd.api.types.is_float_dtype(series.dtype):
        try:
            if (series == series.apply(lambda x: int(x))).all():
                return series.apply(lambda x: str(int(x)))
        except (ValueError, OverflowError):
            pass
    return series.astype(str)


def infer_column_type(series: pd.Series, col_name: str = "") -> ColType:
    s = series.dropna()
    if s.empty:
        return "unknown"
    dtype = series.dtype
    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"
    if pd.api.types.is_numeric_dtype(dtype):
        n_unique = s.nunique()
        if n_unique <= 2 and set(s.unique()).issubset({0, 1}):
            return "boolean"
        if n_unique / len(s) < 0.05 and n_unique <= 20:
            return "categorical"
        # Année → catégoriel
        if _is_likely_year(series, col_name):
            return "categorical"
        # Identifiant explicite → texte
        if _is_likely_identifier(series, col_name):
            return "text"
        # Entier pur → texte (rééchantillonnage exact, pas de KDE)
        if _is_integer_valued(series):
            return "text"
        return "numeric"
    if pd.api.types.is_object_dtype(dtype) or isinstance(dtype, pd.StringDtype):
        n_unique = s.nunique()
        if n_unique / len(s) < 0.10 and n_unique <= 50:
            return "categorical"
        return "text"
    return "unknown"


@dataclass
class ColumnProfile:
    name: str
    col_type: ColType
    null_rate: float
    n_unique: int
    likely_identifier: bool = False
    likely_year: bool = False
    is_integer: bool = False        # True si colonne numérique entière
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    q25: float | None = None
    q50: float | None = None
    q75: float | None = None
    value_counts: dict[Any, float] = field(default_factory=dict)
    avg_length: float | None = None
    sample_values: list[str] = field(default_factory=list)
    dt_min: str | None = None
    dt_max: str | None = None


def profile_dataframe(df: pd.DataFrame) -> dict[str, ColumnProfile]:
    profiles: dict[str, ColumnProfile] = {}
    for col in df.columns:
        series    = df[col]
        is_num    = pd.api.types.is_numeric_dtype(series.dtype)
        likely_id = is_num and _is_likely_identifier(series, col)
        likely_yr = is_num and _is_likely_year(series, col)
        is_int    = is_num and _is_integer_valued(series)
        col_type  = infer_column_type(series, col_name=col)
        n         = len(series)
        null_rate = series.isna().sum() / n if n > 0 else 0.0
        n_unique  = int(series.nunique(dropna=True))

        p = ColumnProfile(
            name=col, col_type=col_type,
            null_rate=float(null_rate), n_unique=n_unique,
            likely_identifier=likely_id, likely_year=likely_yr,
            is_integer=is_int,
        )
        s = series.dropna()

        if col_type == "numeric":
            p.mean = float(s.mean())
            p.std  = float(s.std())
            p.min  = float(s.min())
            p.max  = float(s.max())
            p.q25  = float(s.quantile(0.25))
            p.q50  = float(s.quantile(0.50))
            p.q75  = float(s.quantile(0.75))
        elif col_type in {"categorical", "boolean"}:
            vc = s.value_counts(normalize=True)
            if likely_yr:
                p.value_counts = {str(int(float(k))): float(v) for k, v in vc.items()}
            else:
                p.value_counts = {
                    (str(k.date()) if hasattr(k, 'date') else str(k)): float(v)
                    for k, v in vc.items()
                }
        elif col_type == "text":
            # Conversion propre pour les entiers numériques requalifiés en texte
            str_series      = _to_str_clean(s)
            p.avg_length    = float(str_series.str.len().mean())
            p.sample_values = str_series.sample(min(5, len(str_series)), random_state=0).tolist()
        elif col_type == "datetime":
            p.dt_min = str(s.min())
            p.dt_max = str(s.max())

        profiles[col] = p
    return profiles
