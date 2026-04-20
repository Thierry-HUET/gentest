"""
layout.py – Pages / sections de l'application Streamlit.
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from gentest.core.loader import load_file
from gentest.core.profiler import profile_dataframe, ColumnProfile
from gentest.core.correlations import detect_sensitive_pairs, sensitive_only, CorrelationPair
from gentest.core.generator import generate, GeneratorConfig
from gentest.core.validator import build_report, ConformityReport
from gentest.ui.components import (
    inject_styles,
    section_header,
    card,
    progress_badge,
    alert,
    accordion,
    COLOR_PRIMARY,
    COLOR_DANGER,
)


# ---------------------------------------------------------------------------
# Helpers export
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


def _reason_cell(reason: str) -> str:
    if not reason:
        return "—"
    return f'<span style="color:{COLOR_DANGER}; font-size:.8rem;">{reason}</span>'


def _report_html(report: ConformityReport) -> str:
    rows_col = "".join(
        f"<tr>"
        f"<td>{r.name}</td><td>{r.col_type}</td>"
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
    <h2>Rapport de conformité</h2>
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
# Application principale
# ---------------------------------------------------------------------------
def run_app() -> None:
    st.set_page_config(
        page_title="gentest – Générateur de jeu de test",
        page_icon="🧪",
        layout="wide",
    )
    inject_styles()

    # ---- Sidebar -----------------------------------------------------------
    with st.sidebar:
        st.markdown(
            "<h4 style='color:#fff;margin-bottom:1rem;'>🧪 gentest</h4>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown(
            "<p style='font-size:.85rem;font-weight:600;margin-bottom:4px;'>Paramètres de génération</p>",
            unsafe_allow_html=True,
        )
        n_rows = st.number_input("Nombre de lignes", min_value=10, max_value=1_000_000, value=1000, step=100)
        seed   = st.number_input("Seed (reproductibilité)", min_value=0, value=42)
        st.markdown("---")
        st.markdown(
            "<p style='font-size:.85rem;font-weight:600;margin-bottom:4px;'>Tolérances de conformité</p>",
            unsafe_allow_html=True,
        )
        tolerance      = st.slider("Tolérance numérique (%)", 1, 20, 5) / 100
        js_threshold   = st.slider("Seuil Jensen-Shannon", 0.01, 0.20, 0.05, step=0.01)
        regex_min_rate = st.slider("Conformité regex min. (%)", 50, 100, 95) / 100

    # ---- En-tête -----------------------------------------------------------
    st.markdown(
        f"<h3 style='color:{COLOR_PRIMARY};margin-bottom:.25rem;'>"
        f"Générateur de jeu de test statistiquement conforme</h3>"
        f"<p style='color:#6c757d;font-size:.9rem;margin-bottom:1.5rem;'>"
        f"Chargez un fichier tabulaire, configurez les paramètres et exportez un jeu synthétique conforme.</p>",
        unsafe_allow_html=True,
    )

    # ---- Étape 1 : Chargement ---------------------------------------------
    section_header("① Chargement du fichier source", "CSV · XLSX · Parquet")
    uploaded = st.file_uploader(
        "Déposez un fichier ici",
        type=["csv", "xlsx", "xls", "parquet"],
        label_visibility="collapsed",
    )

    if uploaded is None:
        alert("Aucun fichier chargé. Déposez un fichier CSV, XLSX ou Parquet pour commencer.")
        return

    try:
        df_orig = load_file(uploaded, filename=uploaded.name)
    except Exception as e:
        alert(f"Erreur de chargement : {e}", "danger")
        return

    st.success(f"✓ Fichier chargé — {df_orig.shape[0]} lignes × {df_orig.shape[1]} colonnes")

    with st.expander("Aperçu des données source", expanded=False):
        st.dataframe(df_orig.head(20), width='stretch')

    # ---- Étape 2 : Profil statistique ------------------------------------
    section_header("② Profil statistique", "Inférence automatique des types")

    profiles = profile_dataframe(df_orig)

    rows_html = "".join(
        f"<tr><td>{p.name}</td>"
        f"<td><span class='gt-badge'>{p.col_type}</span></td>"
        f"<td>{p.null_rate:.1%}</td>"
        f"<td>{p.n_unique}</td></tr>"
        for p in profiles.values()
    )
    st.markdown(
        f"<table class='gt-table'>"
        f"<thead><tr><th>Colonne</th><th>Type inféré</th><th>Taux nuls</th><th>Valeurs uniques</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table>",
        unsafe_allow_html=True,
    )

    # ---- Étape 3 : Corrélations ------------------------------------------
    section_header("③ Corrélations sensibles", "|r| > 0.7 — sélectionnez les paires à contraindre")

    all_pairs  = detect_sensitive_pairs(df_orig, profiles)
    sens_pairs = sensitive_only(all_pairs)
    constrained_pairs: list[CorrelationPair] = []

    if not sens_pairs:
        alert("Aucune corrélation sensible détectée dans le jeu de données.")
    else:
        pair_labels = [
            f"{p.col_a} ↔ {p.col_b}  ({p.method}, r={p.coefficient:.2f})"
            for p in sens_pairs
        ]
        selected = st.multiselect(
            "Paires à contraindre lors de la génération",
            options=pair_labels,
            default=pair_labels,
        )
        constrained_pairs = [p for p, lbl in zip(sens_pairs, pair_labels) if lbl in selected]

    # ---- Étape 4 : Regex (texte) — accordéon -----------------------------
    text_cols = [col for col, p in profiles.items() if p.col_type == "text"]
    regex_map: dict[str, str] = {}

    if text_cols:
        section_header("④ Regex par colonne texte", "Développez chaque colonne pour en savoir plus (optionnel)")

        acc_items: list[tuple[str, str]] = []
        for col in text_cols:
            p = profiles[col]
            samples = ", ".join(f"<em>{v}</em>" for v in p.sample_values[:3]) if p.sample_values else "—"
            body = (
                f"<p><strong>Exemples :</strong> {samples}</p>"
                f"<p style='color:#6c757d;margin-top:4px;'>"
                f"Longueur moyenne : {p.avg_length:.1f} car. — "
                f"Laissez le champ vide pour rééchantillonner depuis les données source.</p>"
            )
            acc_items.append((f"🔤 {col}", body))

        accordion(acc_items)

        for col in text_cols:
            pat = st.text_input(
                f"Pattern regex – {col}",
                value="",
                placeholder="ex: [A-Z]{2}\\d{4}",
                key=f"regex_{col}",
            )
            if pat.strip():
                regex_map[col] = pat.strip()

    # ---- Étape 5 : Génération --------------------------------------------
    section_header("⑤ Génération")

    if st.button("▶ Générer le jeu de test", type="primary", width='stretch'):
        with st.spinner("Génération en cours…"):
            config = GeneratorConfig(
                n_rows=int(n_rows),
                seed=int(seed),
                regex_map=regex_map,
                constrained_pairs=constrained_pairs,
            )
            try:
                df_synt = generate(df_orig, profiles, config)
                st.session_state["df_synt"]           = df_synt
                st.session_state["profiles"]          = profiles
                st.session_state["constrained_pairs"] = constrained_pairs
                st.session_state["config"] = {
                    "tolerance":      tolerance,
                    "js_threshold":   js_threshold,
                    "regex_min_rate": regex_min_rate,
                    "regex_map":      regex_map,
                }
                st.success(f"✓ Jeu synthétique généré — {df_synt.shape[0]} lignes × {df_synt.shape[1]} colonnes")
            except Exception as e:
                alert(f"Erreur lors de la génération : {e}", "danger")
                return

    # ---- Étape 6 : Rapport -----------------------------------------------
    if "df_synt" not in st.session_state:
        return

    df_synt = st.session_state["df_synt"]
    cfg     = st.session_state["config"]

    section_header("⑥ Rapport de conformité")

    report = build_report(
        df_original=df_orig,
        df_synthetic=df_synt,
        profiles_original=st.session_state["profiles"],
        constrained_pairs=st.session_state["constrained_pairs"],
        tolerance=cfg["tolerance"],
        js_threshold=cfg["js_threshold"],
        regex_compliance=cfg["regex_min_rate"],
        regex_map=cfg["regex_map"],
    )

    progress_badge("Score global de conformité", report.global_score)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<p style='font-weight:600;margin-bottom:6px;'>Colonnes</p>", unsafe_allow_html=True)
        rows = "".join(
            f"<tr><td>{r.name}</td>"
            f"<td><span class='gt-badge'>{r.col_type}</span></td>"
            f"<td><span class=\"{'gt-ok' if r.compliant else 'gt-ko'}\">"
            f"{'✓ OK' if r.compliant else '✗ KO'}</span></td>"
            f"<td>{_reason_cell(r.reason if not r.compliant else '')}</td></tr>"
            for r in report.column_reports
        )
        st.markdown(
            f"<table class='gt-table'><thead>"
            f"<tr><th>Colonne</th><th>Type</th><th>Statut</th><th>Motif KO</th></tr>"
            f"</thead><tbody>{rows}</tbody></table>",
            unsafe_allow_html=True,
        )

    with col2:
        if report.correlation_reports:
            st.markdown("<p style='font-weight:600;margin-bottom:6px;'>Corrélations contraintes</p>", unsafe_allow_html=True)
            rows_c = "".join(
                f"<tr><td>{r.col_a}</td><td>{r.col_b}</td>"
                f"<td>{r.r_original:.3f}</td><td>{r.r_synthetic:.3f}</td>"
                f"<td>{r.delta:.3f}</td>"
                f"<td><span class=\"{'gt-ok' if r.compliant else 'gt-ko'}\">"
                f"{'✓' if r.compliant else '✗'}</span></td>"
                f"<td>{_reason_cell(r.reason if not r.compliant else '')}</td></tr>"
                for r in report.correlation_reports
            )
            st.markdown(
                f"<table class='gt-table'><thead>"
                f"<tr><th>A</th><th>B</th><th>r orig.</th><th>r synt.</th>"
                f"<th>Δ</th><th>OK</th><th>Motif KO</th></tr>"
                f"</thead><tbody>{rows_c}</tbody></table>",
                unsafe_allow_html=True,
            )
        else:
            alert("Aucune paire de corrélations contrainte.")

    with st.expander("Aperçu du jeu synthétique", expanded=False):
        st.dataframe(df_synt.head(20), width='stretch')

    # ---- Étape 7 : Export ------------------------------------------------
    section_header("⑦ Export")

    export_fmt = st.radio("Format d'export", ["csv", "xlsx", "parquet"], horizontal=True)
    export_bytes = _to_bytes(df_synt, export_fmt)
    mime_map = {
        "csv":     "text/csv",
        "xlsx":    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "parquet": "application/octet-stream",
    }

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            label=f"⬇ Télécharger le jeu synthétique (.{export_fmt})",
            data=export_bytes,
            file_name=f"gentest_synthetic.{export_fmt}",
            mime=mime_map[export_fmt],
            width='stretch',
        )
    with col_b:
        st.download_button(
            label="⬇ Télécharger le rapport (.html)",
            data=_report_html(report).encode(),
            file_name="gentest_report.html",
            mime="text/html",
            width='stretch',
        )
