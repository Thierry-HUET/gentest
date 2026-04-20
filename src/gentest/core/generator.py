"""
generator.py – Génération synthétique d'un DataFrame.

Stratégies par type (REQ-STA-01/02/03) :
  - numeric  : rééchantillonnage KDE + clip sur [min, max]
  - datetime : interpolation uniforme sur [min, max]
  - categorical/boolean : rééchantillonnage selon fréquences observées
  - text     : rééchantillonnage ou génération conforme à une regex
  - Corrélations validées : copule gaussienne (Cholesky)
"""
from __future__ import annotations

import re
import random
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
from scipy import stats

from gentest.core.profiler import ColumnProfile
from gentest.core.correlations import CorrelationPair


@dataclass
class GeneratorConfig:
    n_rows: int = 1000
    seed: int = 42
    # Regex par colonne  {col_name: pattern}
    regex_map: dict[str, str] = field(default_factory=dict)
    # Paires de corrélations à contraindre (validées par l'utilisateur)
    constrained_pairs: list[CorrelationPair] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Génération texte conforme à une regex (approche simplifiée)
# ---------------------------------------------------------------------------
_REGEX_CHARSETS = {
    r"\d": "0123456789",
    r"\w": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
    r"\s": " ",
    r"."  : "abcdefghijklmnopqrstuvwxyz",
}

def _generate_from_regex(pattern: str, rng: random.Random) -> str:
    """Génère une valeur simple correspondant à un pattern regex basique."""
    # Pour les patterns complexes, on utilise la bibliothèque rstr si disponible
    try:
        import rstr
        return rstr.xeger(pattern)
    except ImportError:
        pass
    # Fallback : génération naïve pour patterns simples du type [A-Z]{2}\d{4}
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


# ---------------------------------------------------------------------------
# Générateur principal
# ---------------------------------------------------------------------------
def generate(
    df_original: pd.DataFrame,
    profiles: dict[str, ColumnProfile],
    config: GeneratorConfig,
) -> pd.DataFrame:
    """
    Génère un DataFrame synthétique de config.n_rows lignes.
    """
    rng_np = np.random.default_rng(config.seed)
    rng_py = random.Random(config.seed)
    n = config.n_rows

    # --- 1. Colonnes numériques : KDE ou uniforme si peu de valeurs --------
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

    # --- 2. Contraintes de corrélation (copule gaussienne / Cholesky) ------
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
            # Assurer que la matrice est définie positive
            eigvals = np.linalg.eigvalsh(corr_matrix)
            if eigvals.min() <= 0:
                corr_matrix += np.eye(k) * (abs(eigvals.min()) + 1e-6)

            try:
                L = np.linalg.cholesky(corr_matrix)
                z = rng_np.standard_normal((k, n))
                correlated = (L @ z).T  # shape (n, k)
                # Transformer via quantiles pour préserver les marginales
                for idx, col in enumerate(constrained_cols):
                    u = stats.norm.cdf(correlated[:, idx])
                    src = df_original[col].dropna().values.astype(float)
                    src.sort()
                    quantile_indices = np.clip(
                        (u * len(src)).astype(int), 0, len(src) - 1
                    )
                    numeric_data[col] = src[quantile_indices]
            except np.linalg.LinAlgError:
                pass  # Fallback : on garde les données non contraintes

    # --- 3. Construction du DataFrame --------------------------------------
    out: dict[str, list] = {}

    for col in df_original.columns:
        p = profiles[col]
        null_mask = rng_np.random(n) < p.null_rate

        if p.col_type == "numeric":
            values = numeric_data[col].copy()
            arr = values.tolist()
            for i in range(n):
                if null_mask[i]:
                    arr[i] = None
            out[col] = arr

        elif p.col_type in {"categorical", "boolean"}:
            modalities = list(p.value_counts.keys())
            freqs = list(p.value_counts.values())
            choices = rng_np.choice(modalities, size=n, p=np.array(freqs) / sum(freqs))
            arr = choices.tolist()
            for i in range(n):
                if null_mask[i]:
                    arr[i] = None
            out[col] = arr

        elif p.col_type == "text":
            pattern = config.regex_map.get(col)
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
            t_min = src.min().value  # nanoseconds
            t_max = src.max().value
            ts = rng_np.integers(t_min, t_max, size=n)
            dts = pd.to_datetime(ts)
            arr = dts.tolist()
            for i in range(n):
                if null_mask[i]:
                    arr[i] = None
            out[col] = arr

        else:
            # unknown → rééchantillonnage brut
            src_values = df_original[col].tolist()
            out[col] = [rng_py.choice(src_values) for _ in range(n)]

    return pd.DataFrame(out, columns=df_original.columns)
