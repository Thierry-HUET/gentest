"""
page_home.py – Page d'accueil Midara.

Contenu :
  - En-tête (titre, description)
  - Chargement du fichier source
  - Aperçu des données en accordéon
  - Génération du jeu de test + score de conformité
  - Export
"""
from __future__ import annotations

import io
import base64 as _b64

import pandas as pd
import streamlit as st

from anonyx.core.loader import load_file
from anonyx.core.profiler import profile_dataframe
from anonyx.core.correlations import detect_sensitive_pairs, sensitive_only, CorrelationPair
from anonyx.core.bivariate import compute_bivariate
from anonyx.core.generator import generate, GeneratorConfig
from anonyx.core.validator import build_report
from anonyx.core.logger import get_logger
from anonyx.ui.components import (
    alert,
    progress_badge,
    section_header,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    LOGO_APP_B64,
    _VERSION,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Session keys gérées dans cette page
# ---------------------------------------------------------------------------
_SESSION_KEYS = (
    "report", "df_synt", "profiles", "constrained_pairs",
    "tolerance", "regex_map", "bivariate", "bivariate_orig", "export_cache",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_bytes(df: pd.DataFrame, fmt: str) -> bytes:
    buf = io.BytesIO()
    if fmt == "csv":
        buf.write(df.to_csv(index=False).encode())
    elif fmt == "xlsx":
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False)
    elif fmt == "parquet":
        df.to_parquet(buf, index=False)
    return buf.getvalue()


def _reset_session() -> None:
    for k in _SESSION_KEYS:
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# Blocs de rendu
# ---------------------------------------------------------------------------
def _render_header() -> None:
    """En-tête Midara."""
    if LOGO_APP_B64:
        col_logo, col_text = st.columns([1, 6])
        with col_logo:
            st.image(_b64.b64decode(LOGO_APP_B64))
        with col_text:
            _header_text()
    else:
        _header_text()
    st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)


def _header_text() -> None:
    st.markdown(
        f"<h3 style='color:{COLOR_PRIMARY};margin:0 0 .2rem 0;'><strong>Midara</strong> "
        f"<span style='font-size:.65rem;font-weight:400;color:#aaa;vertical-align:middle;'>v{_VERSION}</span></h3>"
        f"<p style='color:#6c757d;font-size:.9rem;margin:0;line-height:1.6;'>"
        f"<strong style='color:{COLOR_SECONDARY};'>Projet Anonyx</strong> "
        f": pour mieux maîtriser l'exposition de ses données<br>"
        f"Générateur de jeu de test statistiquement conforme</p>",
        unsafe_allow_html=True,
    )


def _render_upload() -> "pd.DataFrame | None":
    """
    Zone de chargement du fichier source.
    Retourne le DataFrame chargé, ou None si aucun fichier.
    """
    section_header("Fichier source", "CSV · XLSX · Parquet")

    uploaded = st.file_uploader(
        "Déposez ou sélectionnez un fichier",
        type=["csv", "xlsx", "xls", "parquet"],
        label_visibility="collapsed",
    )

    if uploaded is None:
        alert(
            "Déposez un fichier CSV, XLSX ou Parquet pour commencer. "
            "Configurez les paramètres de génération dans la barre latérale.",
        )
        return None

    # Reset si fichier changé
    if st.session_state.get("_current_file") != uploaded.name:
        _reset_session()
        st.session_state["_current_file"] = uploaded.name

    try:
        df = load_file(uploaded, filename=uploaded.name)
    except Exception as e:
        log.error("Chargement '%s' échoué", uploaded.name, exc_info=True)
        alert(f"Erreur de chargement : {e}", "danger")
        return None

    # Stocker la référence pour page_stats
    st.session_state["_df_orig_ref"] = df

    st.success(f"✓ {uploaded.name} — {df.shape[0]} lignes × {df.shape[1]} colonnes")
    return df


def _render_preview(df: pd.DataFrame) -> None:
    """Aperçu des données source en accordéon."""
    with st.expander("Aperçu des données source", expanded=False):
        st.dataframe(df.head(20), use_container_width=True)
        col_a, col_b = st.columns(2)
        col_a.metric("Lignes", f"{df.shape[0]:,}".replace(",", "\u202f"))
        col_b.metric("Colonnes", df.shape[1])


def _render_generate(
    df_orig: pd.DataFrame,
    n_rows: int,
    seed: int,
    tolerance: float,
    js_threshold: float,
    regex_min_rate: float,
) -> None:
    """
    Bloc génération + score de conformité + export.
    Isolé pour faciliter le remplacement ultérieur par un appel API Mirada.
    """
    section_header("Générer le jeu de test")

    # Profil (mis en cache dans la session)
    if "profiles" not in st.session_state or st.session_state.get("_profiled_file") != st.session_state.get("_current_file"):
        with st.spinner("Analyse du fichier…"):
            profiles = profile_dataframe(df_orig)
            st.session_state["profiles"] = profiles
            st.session_state["_profiled_file"] = st.session_state.get("_current_file")
            st.session_state["bivariate_orig"] = compute_bivariate(df_orig, profiles)
    profiles = st.session_state["profiles"]

    if "regex_map" not in st.session_state:
        st.session_state["regex_map"] = {}
    regex_map: dict[str, str] = st.session_state["regex_map"]

    # Corrélations sensibles — sélection silencieuse (toutes contraintes par défaut)
    all_pairs   = detect_sensitive_pairs(df_orig, profiles)
    sens_pairs  = sensitive_only(all_pairs)
    constrained_pairs: list[CorrelationPair] = sens_pairs  # toutes sélectionnées par défaut

    if st.button("▶ Générer", type="primary", use_container_width=True):
        with st.spinner("Génération en cours…"):
            config = GeneratorConfig(
                n_rows=int(n_rows),
                seed=int(seed),
                regex_map=regex_map,
                constrained_pairs=constrained_pairs,
            )
            try:
                df_synt          = generate(df_orig, profiles, config)
                bivariate_result = compute_bivariate(df_orig, profiles, df_synt=df_synt)
                report           = build_report(
                    df_original=df_orig,
                    df_synthetic=df_synt,
                    profiles_original=profiles,
                    constrained_pairs=constrained_pairs,
                    tolerance=tolerance,
                    js_threshold=js_threshold,
                    regex_compliance=regex_min_rate,
                    regex_map=regex_map,
                )
                st.session_state.update({
                    "df_synt":            df_synt,
                    "constrained_pairs":  constrained_pairs,
                    "report":             report,
                    "tolerance":          tolerance,
                    "bivariate":          bivariate_result,
                    "export_cache": {
                        "csv":     _to_bytes(df_synt, "csv"),
                        "xlsx":    _to_bytes(df_synt, "xlsx"),
                        "parquet": _to_bytes(df_synt, "parquet"),
                    },
                })
                st.rerun()
            except Exception as e:
                log.error("Génération échouée", exc_info=True)
                alert(f"Erreur lors de la génération : {e}", "danger")

    # ── Score de conformité ───────────────────────────────────────────────────
    if "report" not in st.session_state:
        return

    report  = st.session_state["report"]
    df_synt = st.session_state["df_synt"]

    st.markdown("<div style='margin-top:1.2rem;'></div>", unsafe_allow_html=True)
    progress_badge("Score de conformité", report.global_score)

    n_ko     = sum(1 for r in report.column_reports if not r.compliant)
    n_cor_ko = sum(1 for r in report.correlation_reports if not r.compliant)

    c1, c2, c3 = st.columns(3)

    def _card(col, label: str, value: str, sub: str, ok: bool) -> None:
        color = COLOR_SUCCESS if ok else COLOR_DANGER
        col.markdown(
            f"<div style='background:#fff;border-left:4px solid {color};"
            f"border-radius:6px;padding:10px 14px;"
            f"box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:4px;'>"
            f"<div style='font-size:.75rem;color:#6c757d;margin-bottom:2px;'>{label}</div>"
            f"<div style='font-size:1.35rem;font-weight:700;color:{color};'>{value}</div>"
            f"<div style='font-size:.75rem;color:#aaa;margin-top:2px;'>{sub}</div></div>",
            unsafe_allow_html=True,
        )

    _card(c1, "Colonnes conformes",
          f"{len(report.column_reports) - n_ko} / {len(report.column_reports)}",
          f"{n_ko} KO" if n_ko else "toutes OK",
          n_ko == 0)
    _card(c2, "Corrélations OK",
          f"{len(report.correlation_reports) - n_cor_ko} / {len(report.correlation_reports)}"
          if report.correlation_reports else "—",
          f"{n_cor_ko} hors tolérance" if n_cor_ko else (
              "toutes OK" if report.correlation_reports else "aucune contrainte"),
          n_cor_ko == 0)
    _card(c3, "Lignes générées",
          f"{len(df_synt):,}".replace(",", "\u202f"),
          "jeu synthétique",
          True)

    if n_ko:
        alert(
            f"{n_ko} colonne(s) non conforme(s). "
            f"Consultez la page <strong>Statistiques</strong> pour le détail.",
            "warning",
        )

    # ── Aperçu synthétique ───────────────────────────────────────────────────
    with st.expander("Aperçu du jeu synthétique", expanded=False):
        st.dataframe(df_synt.head(20), use_container_width=True)


def _render_export() -> None:
    """Bloc export — visible uniquement si un jeu a été généré."""
    if "export_cache" not in st.session_state:
        return

    section_header("Export")

    export_fmt   = st.radio("Format", ["csv", "xlsx", "parquet"], horizontal=True)
    export_cache = st.session_state["export_cache"]
    report       = st.session_state["report"]

    mime_map = {
        "csv":     "text/csv",
        "xlsx":    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "parquet": "application/octet-stream",
    }

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            label=f"⬇ Jeu synthétique (.{export_fmt})",
            data=export_cache[export_fmt],
            file_name=f"midara_synthetic.{export_fmt}",
            mime=mime_map[export_fmt],
            use_container_width=True,
        )
    with col_b:
        st.download_button(
            label="⬇ Rapport de conformité (.html)",
            data=_report_html(report).encode(),
            file_name="midara_report.html",
            mime="text/html",
            use_container_width=True,
        )


def _report_html(report) -> str:
    """Génère le rapport HTML de conformité."""
    rows_col = "".join(
        f"<tr><td>{r.name}</td><td>{r.col_type}</td>"
        f"<td><span class=\"{'badge-ok' if r.compliant else 'badge-ko'}\">"
        f"{'✓' if r.compliant else '✗'}</span></td>"
        f"<td style='color:#c0392b;font-size:.8rem;'>{r.reason if not r.compliant else ''}</td>"
        f"</tr>"
        for r in report.column_reports
    )
    rows_cor = "".join(
        f"<tr><td>{r.col_a}</td><td>{r.col_b}</td>"
        f"<td>{r.r_original:.3f}</td><td>{r.r_synthetic:.3f}</td>"
        f"<td>{r.delta:.3f}</td>"
        f"<td><span class=\"{'badge-ok' if r.compliant else 'badge-ko'}\">"
        f"{'✓' if r.compliant else '✗'}</span></td>"
        f"<td style='color:#c0392b;font-size:.8rem;'>{r.reason if not r.compliant else ''}</td>"
        f"</tr>"
        for r in report.correlation_reports
    )
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
    <style>
      body {{font-family:'Segoe UI',sans-serif;padding:24px;color:#222;}}
      h2 {{color:#006699;}} h3 {{color:#004d73;margin-top:1.5rem;}}
      table {{border-collapse:collapse;width:100%;margin-top:.5rem;}}
      th,td {{border:1px solid #dde3e8;padding:7px 10px;font-size:.88rem;}}
      th {{background:#006699;color:#fff;font-weight:600;text-align:left;}}
      tr:nth-child(even) td {{background:#f5f9fc;}}
      .badge-ok {{background:#198754;color:#fff;padding:2px 7px;border-radius:4px;font-size:.75rem;}}
      .badge-ko {{background:#c0392b;color:#fff;padding:2px 7px;border-radius:4px;font-size:.75rem;}}
    </style></head><body>
    <h2>Midara — Rapport de conformité</h2>
    <p>Score global : <strong>{int(report.global_score * 100)} %</strong></p>
    <h3>Colonnes</h3>
    <table><thead><tr><th>Colonne</th><th>Type</th><th>Statut</th><th>Motif KO</th></tr></thead>
    <tbody>{rows_col}</tbody></table>
    <h3>Corrélations contraintes</h3>
    <table><thead><tr><th>Col A</th><th>Col B</th><th>r orig.</th><th>r synt.</th>
    <th>Δ</th><th>Statut</th><th>Motif KO</th></tr></thead>
    <tbody>{rows_cor}</tbody></table>
    </body></html>"""


# ---------------------------------------------------------------------------
# Point d'entrée de la page
# ---------------------------------------------------------------------------
def render(n_rows: int, seed: int, tolerance: float, js_threshold: float, regex_min_rate: float) -> None:
    """Appelé par layout.py avec les paramètres sidebar."""
    _render_header()

    df_orig = _render_upload()
    if df_orig is None:
        return

    _render_preview(df_orig)
    _render_generate(df_orig, n_rows, seed, tolerance, js_threshold, regex_min_rate)
    _render_export()
