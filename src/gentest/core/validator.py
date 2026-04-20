"""
validator.py – Rapport de conformité entre le jeu d'origine et le jeu synthétique.

Métriques (REQ-VAL-01) :
  - Numérique  : écart relatif sur mean, std, min, max, q25, q50, q75 → tolérance ±5 %
  - Catégoriel : divergence Jensen-Shannon ≤ 0.05
  - Texte      : taux de conformité regex ≥ 95 %
  - Corrélations validées : écart |r_synt - r_orig| ≤ 0.05
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy import stats

from gentest.core.profiler import ColumnProfile, profile_dataframe
from gentest.core.correlations import CorrelationPair


# ---------------------------------------------------------------------------
# Résultats par colonne
# ---------------------------------------------------------------------------
@dataclass
class ColumnReport:
    name: str
    col_type: str
    compliant: bool
    details: dict       # métrique → {original, synthetic, delta, ok}
    reason: str = ""    # motif KO court (≤ 3 mots), vide si OK


@dataclass
class CorrelationReport:
    col_a: str
    col_b: str
    r_original: float
    r_synthetic: float
    delta: float
    compliant: bool
    reason: str = ""    # motif KO court (≤ 3 mots), vide si OK


@dataclass
class ConformityReport:
    global_score: float
    column_reports: list[ColumnReport] = field(default_factory=list)
    correlation_reports: list[CorrelationReport] = field(default_factory=list)

    @property
    def compliant_columns(self) -> int:
        return sum(1 for r in self.column_reports if r.compliant)

    @property
    def total_columns(self) -> int:
        return len(self.column_reports)


# ---------------------------------------------------------------------------
# Libellés courts des métriques (utilisés dans le motif KO)
# ---------------------------------------------------------------------------
_METRIC_LABEL = {
    "mean":      "moyenne dérivée",
    "std":       "dispersion dérivée",
    "min":       "min dérivé",
    "max":       "max dérivé",
    "q25":       "Q25 dérivé",
    "q50":       "médiane dérivée",
    "q75":       "Q75 dérivé",
    "null_rate": "nulls dérivés",
}


# ---------------------------------------------------------------------------
# Fonctions internes
# ---------------------------------------------------------------------------
def _relative_error(orig: float, synt: float) -> float:
    if orig == 0:
        return abs(synt)
    return abs(synt - orig) / abs(orig)


def _build_numeric_reason(details: dict) -> str:
    """Retourne les libellés courts des métriques KO, séparés par une virgule."""
    failures = [
        _METRIC_LABEL.get(m, m)
        for m, info in details.items()
        if not info.get("ok", True)
    ]
    return ", ".join(failures)


def _validate_numeric(
    p_orig: ColumnProfile,
    p_synt: ColumnProfile,
    tolerance: float,
) -> ColumnReport:
    metrics = {
        "mean": (p_orig.mean, p_synt.mean),
        "std":  (p_orig.std,  p_synt.std),
        "min":  (p_orig.min,  p_synt.min),
        "max":  (p_orig.max,  p_synt.max),
        "q25":  (p_orig.q25,  p_synt.q25),
        "q50":  (p_orig.q50,  p_synt.q50),
        "q75":  (p_orig.q75,  p_synt.q75),
    }
    details = {}
    all_ok = True
    for metric, (orig, synt) in metrics.items():
        if orig is None or synt is None:
            continue
        delta = _relative_error(orig, synt)
        ok = delta <= tolerance
        details[metric] = {"original": orig, "synthetic": synt, "delta": delta, "ok": ok}
        if not ok:
            all_ok = False

    delta_null = abs(p_synt.null_rate - p_orig.null_rate)
    ok_null = delta_null <= tolerance
    details["null_rate"] = {
        "original": p_orig.null_rate,
        "synthetic": p_synt.null_rate,
        "delta": delta_null,
        "ok": ok_null,
    }
    if not ok_null:
        all_ok = False

    reason = "" if all_ok else _build_numeric_reason(details)
    return ColumnReport(name=p_orig.name, col_type="numeric", compliant=all_ok, details=details, reason=reason)


def _validate_categorical(
    p_orig: ColumnProfile,
    p_synt: ColumnProfile,
    js_threshold: float,
) -> ColumnReport:
    all_keys = set(p_orig.value_counts) | set(p_synt.value_counts)
    p = np.array([p_orig.value_counts.get(k, 0.0) for k in all_keys])
    q = np.array([p_synt.value_counts.get(k, 0.0) for k in all_keys])
    p = p / p.sum() if p.sum() > 0 else p
    q = q / q.sum() if q.sum() > 0 else q

    js = float(jensenshannon(p, q) ** 2)
    ok = js <= js_threshold
    details = {
        "jensen_shannon": {
            "original": 0.0,
            "synthetic": js,
            "delta": js,
            "ok": ok,
            "threshold": js_threshold,
        }
    }
    reason = "" if ok else "distribution divergente"
    return ColumnReport(name=p_orig.name, col_type=p_orig.col_type, compliant=ok, details=details, reason=reason)


def _validate_text(
    df_synt: pd.DataFrame,
    col: str,
    regex_map: dict[str, str],
    min_compliance: float,
) -> ColumnReport:
    pattern = regex_map.get(col)
    if not pattern:
        details = {"regex": {"ok": True, "note": "Aucune regex définie"}}
        return ColumnReport(name=col, col_type="text", compliant=True, details=details)

    values = df_synt[col].dropna().astype(str)
    rate = float(values.apply(lambda v: bool(re.fullmatch(pattern, v))).mean()) if not values.empty else 0.0

    ok = rate >= min_compliance
    details = {
        "regex_compliance": {
            "original": min_compliance,
            "synthetic": rate,
            "delta": abs(rate - min_compliance),
            "ok": ok,
            "pattern": pattern,
        }
    }
    reason = "" if ok else "regex non conforme"
    return ColumnReport(name=col, col_type="text", compliant=ok, details=details, reason=reason)


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------
def build_report(
    df_original: pd.DataFrame,
    df_synthetic: pd.DataFrame,
    profiles_original: dict[str, ColumnProfile],
    constrained_pairs: list[CorrelationPair],
    tolerance: float = 0.05,
    js_threshold: float = 0.05,
    regex_compliance: float = 0.95,
    regex_map: dict[str, str] | None = None,
) -> ConformityReport:
    """Produit le rapport de conformité complet."""
    regex_map = regex_map or {}
    profiles_synt = profile_dataframe(df_synthetic)

    column_reports: list[ColumnReport] = []

    for col, p_orig in profiles_original.items():
        p_synt = profiles_synt.get(col)
        if p_synt is None:
            continue

        if p_orig.col_type == "numeric":
            column_reports.append(_validate_numeric(p_orig, p_synt, tolerance))
        elif p_orig.col_type in {"categorical", "boolean"}:
            column_reports.append(_validate_categorical(p_orig, p_synt, js_threshold))
        elif p_orig.col_type == "text":
            column_reports.append(_validate_text(df_synthetic, col, regex_map, regex_compliance))
        else:
            column_reports.append(
                ColumnReport(name=col, col_type=p_orig.col_type, compliant=True, details={})
            )

    # Corrélations validées
    correlation_reports: list[CorrelationReport] = []
    for pair in constrained_pairs:
        sub_orig = df_original[[pair.col_a, pair.col_b]].dropna()
        sub_synt = df_synthetic[[pair.col_a, pair.col_b]].dropna()
        if len(sub_orig) < 5 or len(sub_synt) < 5:
            continue

        if pair.method == "pearson":
            r_orig, _ = stats.pearsonr(sub_orig[pair.col_a], sub_orig[pair.col_b])
            r_synt, _ = stats.pearsonr(sub_synt[pair.col_a], sub_synt[pair.col_b])
        else:
            r_orig, _ = stats.spearmanr(sub_orig[pair.col_a], sub_orig[pair.col_b])
            r_synt, _ = stats.spearmanr(sub_synt[pair.col_a], sub_synt[pair.col_b])

        delta = abs(float(r_synt) - float(r_orig))
        compliant = delta <= tolerance
        reason = "" if compliant else "corrélation non préservée"
        correlation_reports.append(
            CorrelationReport(
                col_a=pair.col_a,
                col_b=pair.col_b,
                r_original=float(r_orig),
                r_synthetic=float(r_synt),
                delta=delta,
                compliant=compliant,
                reason=reason,
            )
        )

    all_ok = [r.compliant for r in column_reports] + [r.compliant for r in correlation_reports]
    global_score = sum(all_ok) / len(all_ok) if all_ok else 1.0

    return ConformityReport(
        global_score=global_score,
        column_reports=column_reports,
        correlation_reports=correlation_reports,
    )
