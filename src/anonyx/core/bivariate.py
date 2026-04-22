"""
bivariate.py – Statistiques bivariées toutes paires + filtrage spectral.

Pipeline :
  1. Calcul d'un score d'association normalisé [0,1] pour chaque paire de colonnes
     selon le type sémantique des deux colonnes :
       - Numérique × Numérique : r² de Pearson (ou Spearman si non-linéaire)
       - Catégoriel × Catégoriel : V de Cramér
       - Numérique × Catégoriel : η² (rapport de corrélation)
       - Booléen               : traité comme catégoriel
       - Texte / Datetime      : exclus (pas de sémantique bivariée utile)
  2. Construction d'une matrice d'association symétrique N×N
  3. Filtrage spectral (valeurs propres > 1, critère de Kaiser) :
     - Décomposition spectrale de la matrice
     - Calcul de la contribution de chaque colonne aux axes significatifs (cos²)
     - Conservation des colonnes dont la contribution >= contribution moyenne
  4. Export de la sous-matrice filtrée et des métadonnées de type de paire
"""
from __future__ import annotations

import warnings
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import chi2_contingency

from anonyx.core.profiler import ColumnProfile
from anonyx.core.logger import get_logger

log = get_logger(__name__)

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=stats.ConstantInputWarning)


# ---------------------------------------------------------------------------
# Types de paires
# ---------------------------------------------------------------------------
PAIR_NUM_NUM = "num×num"
PAIR_CAT_CAT = "cat×cat"
PAIR_NUM_CAT = "num×cat"

_ELIGIBLE_TYPES = {"numeric", "categorical", "boolean"}


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------
@dataclass
class PairStat:
    col_a:      str
    col_b:      str
    pair_type:  str           # PAIR_NUM_NUM | PAIR_CAT_CAT | PAIR_NUM_CAT
    score_orig: float         # score association [0,1] sur jeu original
    score_synt: float = 0.0   # score association [0,1] sur jeu synthétique
    delta:      float = 0.0   # |score_synt - score_orig|


@dataclass
class BivariateResult:
    columns:     list[str]                    # colonnes retenues après filtrage
    matrix_orig: np.ndarray                   # matrice filtrée jeu original
    matrix_synt: np.ndarray | None = None     # matrice filtrée jeu synthétique
    pair_types:  dict[tuple[str, str], str] = field(default_factory=dict)
    eigvals:     list[float] = field(default_factory=list)
    n_significant: int = 0                    # nombre de VP > 1


# ---------------------------------------------------------------------------
# Scores d'association
# ---------------------------------------------------------------------------
def _pearson_r2(s1: pd.Series, s2: pd.Series) -> float:
    mask = s1.notna() & s2.notna()
    if mask.sum() < 5:
        return 0.0
    try:
        r, _ = stats.pearsonr(s1[mask].astype(float), s2[mask].astype(float))
        return float(r ** 2) if not np.isnan(r) else 0.0
    except Exception:
        return 0.0


def _cramers_v(s1: pd.Series, s2: pd.Series) -> float:
    idx = s1.dropna().index.intersection(s2.dropna().index)
    if len(idx) < 5:
        return 0.0
    try:
        ct = pd.crosstab(s1.loc[idx], s2.loc[idx])
        if ct.shape[0] < 2 or ct.shape[1] < 2:
            return 0.0
        chi2, _, _, _ = chi2_contingency(ct)
        n = ct.values.sum()
        phi2 = chi2 / n
        r, k = ct.shape
        v = np.sqrt(phi2 / max(min(k - 1, r - 1), 1))
        return float(min(1.0, v))
    except Exception:
        return 0.0


def _eta_squared(num_s: pd.Series, cat_s: pd.Series) -> float:
    mask = num_s.notna() & cat_s.notna()
    num_s, cat_s = num_s[mask].astype(float), cat_s[mask]
    if len(num_s) < 5:
        return 0.0
    try:
        grand_mean = num_s.mean()
        ss_between = sum(
            len(g) * (g.mean() - grand_mean) ** 2
            for grp in cat_s.unique()
            if len(g := num_s[cat_s == grp]) > 0
        )
        ss_total = ((num_s - grand_mean) ** 2).sum()
        return float(min(1.0, ss_between / ss_total)) if ss_total > 0 else 0.0
    except Exception:
        return 0.0


def _assoc_score(
    df: pd.DataFrame,
    c1: str, c2: str,
    t1: str, t2: str,
) -> tuple[float, str]:
    """Retourne (score, type_paire)."""
    is_num1 = t1 == "numeric"
    is_num2 = t2 == "numeric"

    if is_num1 and is_num2:
        return _pearson_r2(df[c1], df[c2]), PAIR_NUM_NUM
    elif not is_num1 and not is_num2:
        return _cramers_v(df[c1], df[c2]), PAIR_CAT_CAT
    else:
        nc = c1 if is_num1 else c2
        cc = c1 if not is_num1 else c2
        return _eta_squared(df[nc], df[cc]), PAIR_NUM_CAT


# ---------------------------------------------------------------------------
# Construction de la matrice d'association
# ---------------------------------------------------------------------------
def _build_matrix(
    df: pd.DataFrame,
    cols: list[str],
    col_types: dict[str, str],
) -> tuple[np.ndarray, dict[tuple[str, str], str]]:
    n = len(cols)
    M = np.eye(n)
    pair_types: dict[tuple[str, str], str] = {}

    for i in range(n):
        for j in range(i + 1, n):
            c1, c2 = cols[i], cols[j]
            t1 = "numeric" if col_types[c1] == "numeric" else "categorical"
            t2 = "numeric" if col_types[c2] == "numeric" else "categorical"
            score, ptype = _assoc_score(df, c1, c2, t1, t2)
            M[i, j] = M[j, i] = score
            pair_types[(c1, c2)] = ptype
            pair_types[(c2, c1)] = ptype

    return M, pair_types


# ---------------------------------------------------------------------------
# Filtrage spectral (critère de Kaiser : lambda > 1)
# ---------------------------------------------------------------------------
def _spectral_filter(
    cols: list[str],
    M: np.ndarray,
    kaiser_threshold: float = 1.0,
) -> tuple[list[str], list[int], list[float], int]:
    """
    Retourne (colonnes_retenues, indices_retenus, valeurs_propres, n_significant).
    """
    eigvals, eigvecs = np.linalg.eigh(M)
    eigvals_sorted = eigvals[::-1]

    sig_mask = eigvals > kaiser_threshold
    n_sig = int(sig_mask.sum())

    if n_sig == 0:
        # Fallback : on garde au moins la première VP
        sig_mask = eigvals == eigvals.max()
        n_sig = 1

    # cos² de chaque colonne sur les axes significatifs
    contrib = np.sum(eigvecs[:, sig_mask] ** 2, axis=1)
    mean_contrib = contrib.mean()

    kept_idx = [i for i, c in enumerate(contrib) if c >= mean_contrib]
    if not kept_idx:
        kept_idx = list(range(len(cols)))

    kept_cols = [cols[i] for i in kept_idx]
    return kept_cols, kept_idx, eigvals_sorted.tolist(), n_sig


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------
def compute_bivariate(
    df_orig: pd.DataFrame,
    profiles: dict[str, ColumnProfile],
    df_synt: pd.DataFrame | None = None,
    kaiser_threshold: float = 1.0,
) -> BivariateResult:
    """
    Calcule les statistiques bivariées sur le jeu original (et optionnellement
    sur le jeu synthétique), filtre les colonnes par décomposition spectrale
    et retourne la BivariateResult.
    """
    t0 = time.perf_counter()
    mode = "orig+synt" if df_synt is not None else "orig"

    # Colonnes éligibles (numeric, categorical, boolean)
    eligible = [
        col for col, p in profiles.items()
        if p.col_type in _ELIGIBLE_TYPES
        and col in df_orig.columns
        and df_orig[col].notna().sum() >= 5
    ]

    if len(eligible) < 2:
        log.warning(
            "compute_bivariate [%s] : seulement %d colonne(s) éligible(s), heatmap ignorée",
            mode, len(eligible),
        )
        return BivariateResult(columns=eligible, matrix_orig=np.eye(max(len(eligible), 1)))

    col_types = {col: profiles[col].col_type for col in eligible}

    # Matrice originale
    M_orig, pair_types = _build_matrix(df_orig, eligible, col_types)

    # Filtrage spectral
    kept_cols, kept_idx, eigvals, n_sig = _spectral_filter(
        eligible, M_orig, kaiser_threshold
    )
    M_orig_f = M_orig[np.ix_(kept_idx, kept_idx)]

    log.info(
        "compute_bivariate [%s] : %d/%d colonnes retenues, %d VP>1, en %.2fs",
        mode, len(kept_cols), len(eligible), n_sig, time.perf_counter() - t0,
    )

    # Matrice synthétique (si disponible)
    M_synt_f: np.ndarray | None = None
    if df_synt is not None:
        t1 = time.perf_counter()
        synt_eligible = [c for c in kept_cols if c in df_synt.columns]
        if len(synt_eligible) == len(kept_cols):
            M_synt_full, _ = _build_matrix(df_synt, kept_cols, col_types)
            M_synt_f = M_synt_full
            log.info(
                "compute_bivariate [synt] : matrice %dx%d en %.2fs",
                len(kept_cols), len(kept_cols), time.perf_counter() - t1,
            )
        else:
            log.warning(
                "compute_bivariate [synt] : %d colonne(s) manquante(s) dans le jeu synthétique",
                len(kept_cols) - len(synt_eligible),
            )

    return BivariateResult(
        columns=kept_cols,
        matrix_orig=M_orig_f,
        matrix_synt=M_synt_f,
        pair_types=pair_types,
        eigvals=eigvals,
        n_significant=n_sig,
    )
