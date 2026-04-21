"""
layout.py – Pages / sections de l'application Streamlit — Anonyx·Gen.
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from anonyx.core.loader import load_file
from anonyx.core.profiler import profile_dataframe, ColumnProfile
from anonyx.core.correlations import detect_sensitive_pairs, sensitive_only, CorrelationPair
from anonyx.core.generator import generate, GeneratorConfig
from anonyx.core.validator import build_report, ConformityReport, ColumnReport
from anonyx.ui.components import (
    inject_styles,
    section_header,
    progress_badge,
    alert,
    sidebar_logo,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_LIGHT,
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


def _report_html(report: ConformityReport) -> str:
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
    <h2>Anonyx·Gen — Rapport de conformité</h2>
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
# Rendu d'un expander par colonne
# ---------------------------------------------------------------------------
def _col_expander_title(p: ColumnProfile, cr: ColumnReport | None) -> str:
    type_color = {
        "numeric":     COLOR_PRIMARY,
        "categorical": "#6f42c1",
        "boolean":     "#0d6efd",
        "text":        "#20c997",
        "datetime":    "#fd7e14",
        "unknown":     "#6c757d",
    }.get(p.col_type, COLOR_PRIMARY)

    parts = [
        f"<strong>{p.name}</strong>",
        f"<span style='background:{type_color};color:#fff;padding:1px 6px;"
        f"border-radius:3px;font-size:.72rem;font-weight:600;'>{p.col_type}</span>",
    ]
    if p.likely_identifier:
        parts.append(
            "<span style='background:#fff3cd;color:#7a5c00;padding:1px 6px;"
            "border-radius:3px;font-size:.72rem;font-weight:600;'>⚠ identifiant</span>"
        )
    if p.likely_year:
        parts.append(
            "<span style='background:#e8f4f8;color:#004d73;padding:1px 6px;"
            "border-radius:3px;font-size:.72rem;font-weight:600;'>📅 année</span>"
        )
    if cr is not None:
        if cr.compliant:
            parts.append("<span class='gt-ok'>✓ OK</span>")
        else:
            parts.append(f"<span class='gt-ko'>✗ KO — {cr.reason}</span>")
    return "  ".join(parts)


def _render_profile_section(p: ColumnProfile) -> None:
    st.markdown(
        f"<p style='font-size:.8rem;font-weight:600;color:{COLOR_SECONDARY};"
        f"margin-bottom:4px;'>PROFIL ORIGINAL</p>",
        unsafe_allow_html=True,
    )
    rows = [("Taux nuls", f"{p.null_rate:.1%}"), ("Valeurs uniques", str(p.n_unique))]
    if p.col_type == "numeric":
        rows += [
            ("Moyenne", f"{p.mean:.4g}"), ("Écart-type", f"{p.std:.4g}"),
            ("Min / Max", f"{p.min:.4g} / {p.max:.4g}"),
            ("Q25 / Q50 / Q75", f"{p.q25:.4g} / {p.q50:.4g} / {p.q75:.4g}"),
        ]
    elif p.col_type in {"categorical", "boolean"}:
        for val, freq in list(p.value_counts.items())[:3]:
            rows.append((f"  {val}", f"{freq:.1%}"))
    elif p.col_type == "text":
        rows.append(("Long. moy.", f"{p.avg_length:.1f} car."))
        if p.sample_values:
            rows.append(("Exemples", ", ".join(p.sample_values[:3])))
    elif p.col_type == "datetime":
        rows += [("Min", p.dt_min or "—"), ("Max", p.dt_max or "—")]

    trs = "".join(
        f"<tr><td style='color:#6c757d;font-size:.8rem;padding:2px 6px;'>{k}</td>"
        f"<td style='font-size:.8rem;padding:2px 6px;font-weight:500;'>{v}</td></tr>"
        for k, v in rows
    )
    st.markdown(f"<table style='border-collapse:collapse;width:100%;'>{trs}</table>", unsafe_allow_html=True)


def _render_conformity_section(cr: ColumnReport) -> None:
    st.markdown(
        f"<p style='font-size:.8rem;font-weight:600;color:{COLOR_SECONDARY};"
        f"margin-bottom:4px;'>RÉSULTAT SYNTHÉTIQUE</p>",
        unsafe_allow_html=True,
    )
    if not cr.details:
        st.caption("Aucune métrique disponible.")
        return
    rows = []
    for metric, info in cr.details.items():
        if "note" in info:
            continue
        ok    = info.get("ok", True)
        orig  = info.get("original")
        synt  = info.get("synthetic")
        if orig is not None and synt is not None:
            label    = metric.replace("_", " ").replace("jensen shannon", "JS divergence")
            orig_str = f"{orig:.4g}" if isinstance(orig, float) else str(orig)
            synt_str = f"{synt:.4g}" if isinstance(synt, float) else str(synt)
            rows.append((label, orig_str, synt_str, "✓" if ok else "✗", COLOR_SUCCESS if ok else COLOR_DANGER))

    trs = "".join(
        f"<tr>"
        f"<td style='color:#6c757d;font-size:.8rem;padding:2px 6px;'>{lbl}</td>"
        f"<td style='font-size:.8rem;padding:2px 6px;'>{orig}</td>"
        f"<td style='font-size:.8rem;padding:2px 6px;'>{synt}</td>"
        f"<td style='font-size:.8rem;padding:2px 6px;color:{color};font-weight:700;'>{icon}</td>"
        f"</tr>"
        for lbl, orig, synt, icon, color in rows
    )
    st.markdown(
        f"<table style='border-collapse:collapse;width:100%;'>"
        f"<tr style='font-size:.75rem;color:#aaa;'>"
        f"<th style='padding:2px 6px;font-weight:400;'>Métrique</th>"
        f"<th style='padding:2px 6px;font-weight:400;'>Orig.</th>"
        f"<th style='padding:2px 6px;font-weight:400;'>Synt.</th>"
        f"<th style='padding:2px 6px;'></th></tr>{trs}</table>",
        unsafe_allow_html=True,
    )


def _render_column_expanders(
    profiles: dict[str, ColumnProfile],
    col_reports: dict[str, ColumnReport] | None,
    regex_map: dict[str, str],
) -> None:
    for col, p in profiles.items():
        cr = col_reports.get(col) if col_reports else None
        expanded = cr is not None and not cr.compliant
        status_icon = "" if cr is None else ("✓" if cr.compliant else "✗")
        flags = []
        if p.likely_identifier:
            flags.append("⚠ id")
        if p.likely_year:
            flags.append("📅 année")
        flag_str    = "  " + "  ".join(flags) if flags else ""
        plain_title = f"{status_icon}  {col}  [{p.col_type}{flag_str}]"

        with st.expander(plain_title, expanded=expanded):
            st.markdown(
                f"<div style='margin-bottom:8px;'>{_col_expander_title(p, cr)}</div>",
                unsafe_allow_html=True,
            )
            if p.likely_identifier:
                st.markdown(
                    f"<div style='background:#fff3cd;color:#7a5c00;padding:6px 10px;"
                    f"border-radius:5px;font-size:.82rem;margin-bottom:8px;'>"
                    f"⚠ Identifiant probable — traité comme <strong>texte</strong> "
                    f"(rééchantillonnage). Définissez un pattern regex ci-dessous si besoin.</div>",
                    unsafe_allow_html=True,
                )
            if p.likely_year:
                st.markdown(
                    f"<div style='background:#e8f4f8;color:#004d73;padding:6px 10px;"
                    f"border-radius:5px;font-size:.82rem;margin-bottom:8px;'>"
                    f"📅 Année probable — traité comme <strong>catégoriel</strong> "
                    f"(distribution observée préservée, valeurs entières restituées).</div>",
                    unsafe_allow_html=True,
                )
            left, right = st.columns(2)
            with left:
                _render_profile_section(p)
            with right:
                if cr is not None:
                    _render_conformity_section(cr)
                else:
                    st.caption("Générez le jeu de test pour voir les résultats.")

            if p.col_type == "text":
                st.markdown("<hr style='margin:8px 0;border-color:#dde3e8;'>", unsafe_allow_html=True)
                pat = st.text_input(
                    "Pattern regex (optionnel)", value=regex_map.get(col, ""),
                    placeholder="ex: [A-Z]{2}\\d{4}", key=f"regex_{col}",
                )
                if pat.strip():
                    regex_map[col] = pat.strip()
                elif col in regex_map:
                    del regex_map[col]


# ---------------------------------------------------------------------------
# Application principale
# ---------------------------------------------------------------------------
def run_app() -> None:
    st.set_page_config(
        page_title="Anonyx·Gen – Générateur de jeu de test",
        page_icon="🧪",
        layout="wide",
    )
    inject_styles()

    with st.sidebar:
        st.markdown(
            "<h4 style='color:#fff;margin-bottom:1rem;'>🧪 Anonyx·Gen</h4>",
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
        sidebar_logo()

    st.markdown(
        f"<h3 style='color:{COLOR_PRIMARY};margin-bottom:.25rem;'>Anonyx·Gen</h3>"
        f"<p style='color:#6c757d;font-size:.9rem;margin-bottom:1.5rem;'>"
        f"Générateur de jeu de test statistiquement conforme — "
        f"Chargez un fichier tabulaire, configurez les paramètres et exportez un jeu synthétique.</p>",
        unsafe_allow_html=True,
    )

    section_header("① Chargement du fichier source", "CSV · XLSX · Parquet")
    uploaded = st.file_uploader(
        "Déposez un fichier ici", type=["csv", "xlsx", "xls", "parquet"],
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

    section_header("② Vue par colonne", "Profil · type inféré · résultat synthétique · regex")
    profiles = profile_dataframe(df_orig)

    n_id = sum(1 for p in profiles.values() if p.likely_identifier)
    n_yr = sum(1 for p in profiles.values() if p.likely_year)
    if n_id:
        alert(
            f"⚠ {n_id} colonne(s) requalifiée(s) en <strong>texte</strong> (identifiant probable) : "
            + ", ".join(f"<strong>{p.name}</strong>" for p in profiles.values() if p.likely_identifier),
            "warning",
        )
    if n_yr:
        alert(
            f"📅 {n_yr} colonne(s) requalifiée(s) en <strong>catégoriel</strong> (année probable) : "
            + ", ".join(f"<strong>{p.name}</strong>" for p in profiles.values() if p.likely_year),
            "info",
        )

    if "regex_map" not in st.session_state:
        st.session_state["regex_map"] = {}
    regex_map: dict[str, str] = st.session_state["regex_map"]

    col_reports: dict[str, ColumnReport] | None = None
    if "report" in st.session_state:
        col_reports = {r.name: r for r in st.session_state["report"].column_reports}

    _render_column_expanders(profiles, col_reports, regex_map)

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
            options=pair_labels, default=pair_labels,
        )
        constrained_pairs = [p for p, lbl in zip(sens_pairs, pair_labels) if lbl in selected]

    section_header("④ Génération")
    if st.button("▶ Générer le jeu de test", type="primary", width='stretch'):
        with st.spinner("Génération en cours…"):
            config = GeneratorConfig(
                n_rows=int(n_rows), seed=int(seed),
                regex_map=regex_map, constrained_pairs=constrained_pairs,
            )
            try:
                df_synt = generate(df_orig, profiles, config)
                report  = build_report(
                    df_original=df_orig, df_synthetic=df_synt,
                    profiles_original=profiles, constrained_pairs=constrained_pairs,
                    tolerance=tolerance, js_threshold=js_threshold,
                    regex_compliance=regex_min_rate, regex_map=regex_map,
                )
                st.session_state["df_synt"]           = df_synt
                st.session_state["profiles"]          = profiles
                st.session_state["constrained_pairs"] = constrained_pairs
                st.session_state["report"]            = report
                st.rerun()
            except Exception as e:
                alert(f"Erreur lors de la génération : {e}", "danger")
                return

    if "report" not in st.session_state:
        return

    report  = st.session_state["report"]
    df_synt = st.session_state["df_synt"]

    section_header("⑤ Rapport de conformité", "Score global · corrélations contraintes")
    progress_badge("Score global de conformité", report.global_score)

    n_ko = sum(1 for r in report.column_reports if not r.compliant)
    if n_ko:
        alert(f"{n_ko} colonne(s) non conforme(s) — consultez le détail dans le bloc ② ci-dessus.", "warning")
    else:
        alert("Toutes les colonnes sont conformes.", "success")

    if report.correlation_reports:
        with st.expander("Détail des corrélations contraintes", expanded=False):
            rows_c = "".join(
                f"<tr><td>{r.col_a}</td><td>{r.col_b}</td>"
                f"<td>{r.r_original:.3f}</td><td>{r.r_synthetic:.3f}</td>"
                f"<td>{r.delta:.3f}</td>"
                f"<td><span class=\"{'gt-ok' if r.compliant else 'gt-ko'}\">"
                f"{'✓' if r.compliant else '✗'}</span></td>"
                f"<td style='color:{COLOR_DANGER};font-size:.8rem;'>"
                f"{r.reason if not r.compliant else '—'}</td></tr>"
                for r in report.correlation_reports
            )
            st.markdown(
                f"<table class='gt-table'><thead>"
                f"<tr><th>A</th><th>B</th><th>r orig.</th><th>r synt.</th>"
                f"<th>Δ</th><th>OK</th><th>Motif KO</th></tr>"
                f"</thead><tbody>{rows_c}</tbody></table>",
                unsafe_allow_html=True,
            )

    with st.expander("Aperçu du jeu synthétique", expanded=False):
        st.dataframe(df_synt.head(20), width='stretch')

    section_header("⑥ Export")
    export_fmt   = st.radio("Format d'export", ["csv", "xlsx", "parquet"], horizontal=True)
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
            data=export_bytes, file_name=f"anonyx_gen_synthetic.{export_fmt}",
            mime=mime_map[export_fmt], width='stretch',
        )
    with col_b:
        st.download_button(
            label="⬇ Télécharger le rapport (.html)",
            data=_report_html(report).encode(),
            file_name="anonyx_gen_report.html", mime="text/html", width='stretch',
        )
