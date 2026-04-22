"""
generator.py – Génération synthétique d'un DataFrame.

Stratégies par type :
  - numeric     : KDE float pur (les entiers sont désormais requalifiés en text)
  - categorical : rééchantillonnage selon fréquences observées
  - boolean     : idem categorical
  - text        : rééchantillonnage exact (y compris entiers et identifiants)
  - datetime    : interpolation uniforme sur [min, max]
  - Corrélations validées : copule gaussienne (Cholesky)
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
from scipy import stats

from anonyx.core.profiler import ColumnProfile
from anonyx.core.correlations import CorrelationPair
from anonyx.core.logger import get_logger

log = get_logger(__name__)


@dataclass
class GeneratorConfig:
    n_rows: int = 1000
    seed: int = 42
    regex_map: dict[str, str] = field(default_factory=dict)
    constrained_pairs: list[CorrelationPair] = field(default_factory=list)


def _numeric_col_to_str_list(series: pd.Series) -> list[str]:
    """Série numérique → liste de strings sans suffixe '.0'."""
    s = series.dropna()
    if pd.api.types.is_float_dtype(s.dtype):
        try:
            if (s == s.apply(lambda x: int(x))).all():
                return s.apply(lambda x: str(int(x))).tolist()
        except (ValueError, OverflowError):
            pass
    return s.astype(str).tolist()


def _cast_categorical_value(value: str, profile: ColumnProfile, original_dtype) -> Any:
    if profile.likely_year:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    if pd.api.types.is_integer_dtype(original_dtype):
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    if pd.api.types.is_float_dtype(original_dtype):
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    return value


_REGEX_CHARSETS = {
    r"\d": "0123456789",
    r"\w": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
    r"\s": " ",
    r"." : "abcdefghijklmnopqrstuvwxyz",
}


def _generate_from_regex(pattern: str, rng: random.Random) -> str:
    try:
        import rstr
        return rstr.xeger(pattern)
    except ImportError:
        pass
    result = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            nc = pattern[i + 1]
            charset = _REGEX_CHARSETS.get(f"\\{nc}", "a")
            result.append(rng.choice(charset))
            i += 2
        elif c == "[":
            end = pattern.index("]", i)
            chars = pattern[i + 1:end]
            result.append(rng.choice(list(chars)))
            i = end + 1
        elif c == ".":
            result.append(rng.choice(_REGEX_CHARSETS["."]))
            i += 1
        else:
            result.append(c)
            i += 1
    return "".join(result)


def generate(
    df_original: pd.DataFrame,
    profiles: dict[str, ColumnProfile],
    config: GeneratorConfig,
) -> pd.DataFrame:
    t0     = time.perf_counter()
    rng_np = np.random.default_rng(config.seed)
    rng_py = random.Random(config.seed)
    n      = config.n_rows
    log.info(
        "generate : démarrage — %d lignes, seed=%d, %d paire(s) contrainte(s)",
        n, config.seed, len(config.constrained_pairs),
    )

    # --- 1. Colonnes numériques : KDE float pur ---------------------------
    # Les entiers ont été requalifiés en "text" dans profiler.py
    numeric_cols = [col for col, p in profiles.items() if p.col_type == "numeric"]
    numeric_data: dict[str, np.ndarray] = {}

    for col in numeric_cols:
        p = profiles[col]
        src = df_original[col].dropna().values.astype(float)
        if len(src) >= 4:
            try:
                kde = gaussian_kde(src)
                samples = kde.resample(n, seed=config.seed)[0]
                samples = np.clip(samples, p.min, p.max)
            except Exception:
                samples = rng_np.choice(src, size=n)
        else:
            samples = rng_np.uniform(p.min, p.max, size=n)
        numeric_data[col] = samples

    # --- 2. Contraintes de corrélation (copule Cholesky) ------------------
    if config.constrained_pairs and len(numeric_cols) >= 2:
        constrained_cols = list(
            {col for pair in config.constrained_pairs for col in (pair.col_a, pair.col_b)}
            & set(numeric_cols)
        )
        if len(constrained_cols) >= 2:
            k = len(constrained_cols)
            corr_matrix = np.eye(k)
            col_index = {c: i for i, c in enumerate(constrained_cols)}
            for pair in config.constrained_pairs:
                if pair.col_a in col_index and pair.col_b in col_index:
                    i, j = col_index[pair.col_a], col_index[pair.col_b]
                    corr_matrix[i, j] = pair.coefficient
                    corr_matrix[j, i] = pair.coefficient
            eigvals = np.linalg.eigvalsh(corr_matrix)
            if eigvals.min() <= 0:
                corr_matrix += np.eye(k) * (abs(eigvals.min()) + 1e-6)
            try:
                L = np.linalg.cholesky(corr_matrix)
                z = rng_np.standard_normal((k, n))
                correlated = (L @ z).T
                for idx, col in enumerate(constrained_cols):
                    u = stats.norm.cdf(correlated[:, idx])
                    src = df_original[col].dropna().values.astype(float)
                    src.sort()
                    quantile_indices = np.clip((u * len(src)).astype(int), 0, len(src) - 1)
                    numeric_data[col] = src[quantile_indices]
            except np.linalg.LinAlgError:
                log.warning("generate : copule Cholesky échouée, corrélations ignorées")
                pass

    # --- 3. Construction du DataFrame -------------------------------------
    out: dict[str, list] = {}
    for col in df_original.columns:
        p = profiles[col]
        null_mask  = rng_np.random(n) < p.null_rate
        orig_dtype = df_original[col].dtype

        if p.col_type == "numeric":
            # Float pur — pas d'entiers ici (requalifiés en text)
            arr = numeric_data[col].copy().tolist()
            for i in range(n):
                if null_mask[i]:
                    arr[i] = None
            out[col] = arr

        elif p.col_type in {"categorical", "boolean"}:
            modalities = list(p.value_counts.keys())
            freqs = np.array(list(p.value_counts.values()))
            choices = rng_np.choice(modalities, size=n, p=freqs / freqs.sum())
            arr = [_cast_categorical_value(v, p, orig_dtype) for v in choices.tolist()]
            for i in range(n):
                if null_mask[i]:
                    arr[i] = None
            out[col] = arr

        elif p.col_type == "text":
            pattern = config.regex_map.get(col)
            # Conversion propre pour les colonnes numériques requalifiées en text
            if pd.api.types.is_numeric_dtype(orig_dtype):
                src_values = _numeric_col_to_str_list(df_original[col])
            else:
                src_values = df_original[col].dropna().astype(str).tolist()
            arr = []
            for i in range(n):
                if null_mask[i]:
                    arr.append(None)
                elif pattern:
                    arr.append(_generate_from_regex(pattern, rng_py))
                else:
                    arr.append(rng_py.choice(src_values))
            out[col] = arr

        elif p.col_type == "datetime":
            src = df_original[col].dropna()
            t_min = src.min().value
            t_max = src.max().value
            ts  = rng_np.integers(t_min, t_max, size=n)
            arr = pd.to_datetime(ts).tolist()
            for i in range(n):
                if null_mask[i]:
                    arr[i] = None
            out[col] = arr

        else:
            src_values = df_original[col].tolist()
            out[col] = [rng_py.choice(src_values) for _ in range(n)]

    result = pd.DataFrame(out, columns=df_original.columns)
    log.info(
        "generate : terminé en %.2fs — %d lignes × %d colonnes",
        time.perf_counter() - t0, result.shape[0], result.shape[1],
    )
    return result
