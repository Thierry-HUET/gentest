"""
layout.py – Pages / sections de l'application Streamlit — Midara (Projet Anonyx).
"""
from __future__ import annotations

import io
import base64

import pandas as pd
import streamlit as st

from anonyx.core.loader import load_file
from anonyx.core.profiler import profile_dataframe, ColumnProfile
from anonyx.core.correlations import detect_sensitive_pairs, sensitive_only, CorrelationPair
from anonyx.core.generator import generate, GeneratorConfig
from anonyx.core.validator import build_report, ConformityReport, ColumnReport, CorrelationReport
from anonyx.ui.components import (
    inject_styles,
    section_header,
    progress_badge,
    alert,
    sidebar_logo,
    sidebar_app_logo,
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
# Heatmap SVG des corrélations contraintes
# ---------------------------------------------------------------------------
def _lerp_color(t: float) -> str:
    t = max(0.0, min(1.0, t))
    r = int(25  + t * (192 - 25))
    g = int(135 + t * (57  - 135))
    b = int(84  + t * (43  - 84))
    return f"#{r:02x}{g:02x}{b:02x}"


def _render_correlation_heatmap(reports: list[CorrelationReport], tolerance: float) -> None:
    n = len(reports)
    if n == 0:
        return
    cell_w = 120; cell_h = 64; pad = 8; label_h = 22
    total_w = n * (cell_w + pad) - pad
    total_h = cell_h + label_h + 6
    delta_max = tolerance * 2
    cells = []
    for i, r in enumerate(reports):
        x = i * (cell_w + pad)
        t = min(1.0, r.delta / delta_max) if delta_max > 0 else (0.0 if r.compliant else 1.0)
        color = _lerp_color(t)
        icon  = "✓" if r.compliant else "✗"
        label = f"{r.col_a} ↔ {r.col_b}"
        if len(label) > 20:
            label = label[:18] + "…"
        cells.append(
            f'<g transform="translate({x},0)">'
            f'<rect x="0" y="0" width="{cell_w}" height="{cell_h}" rx="6" fill="{color}"/>'
            f'<text x="{cell_w//2}" y="20" text-anchor="middle" font-size="14" '
            f'font-family="Segoe UI,sans-serif" fill="#fff" font-weight="700">{icon}</text>'
            f'<text x="{cell_w//2}" y="36" text-anchor="middle" font-size="10" '
            f'font-family="Segoe UI,sans-serif" fill="rgba(255,255,255,0.9)">'
            f'{r.r_original:.2f} → {r.r_synthetic:.2f}</text>'
            f'<text x="{cell_w//2}" y="52" text-anchor="middle" font-size="10" '
            f'font-family="Segoe UI,sans-serif" fill="rgba(255,255,255,0.8)">Δ {r.delta:.3f}</text>'
            f'<text x="{cell_w//2}" y="{cell_h+16}" text-anchor="middle" font-size="9" '
            f'font-family="Segoe UI,sans-serif" fill="#444">{label}</text>'
            f'</g>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" '
        f'width="{total_w}" height="{total_h}">' + "".join(cells) + "</svg>"
    )
    c0, c05, c1 = _lerp_color(0.0), _lerp_color(0.5), _lerp_color(1.0)
    html_content = (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        f'body{{margin:0;padding:0;background:transparent;font-family:"Segoe UI",sans-serif;overflow:hidden;}}'
        f'.wrap{{overflow-x:auto;padding:2px 0;}}.legend{{font-size:11px;color:#888;margin-top:6px;}}'
        f'</style></head><body><div class="wrap">{svg}</div>'
        f'<p class="legend">Couleur : '
        f'<span style="color:{c0};font-weight:700;">■ conforme</span> → '
        f'<span style="color:{c05};font-weight:700;">■ limite</span> → '
        f'<span style="color:{c1};font-weight:700;">■ non conforme</span>'
        f' &nbsp;·&nbsp; Rouge complet : Δ ≥ {delta_max:.3f}</p></body></html>'
    )
    b64 = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")
    st.iframe(f"data:text/html;base64,{b64}", height=total_h + 42, scrolling=False)


# ---------------------------------------------------------------------------
# Tableau comparatif Profil original / Résultat synthétique
# ---------------------------------------------------------------------------
def _fmt(v: object) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def _profile_rows(p: ColumnProfile) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = [
        ("null_rate", "Taux nuls", f"{p.null_rate:.1%}"),
    ]
    if p.col_type == "numeric":
        rows += [
            ("mean", "Moyenne",    _fmt(p.mean)),
            ("std",  "Écart-type", _fmt(p.std)),
            ("min",  "Min",        _fmt(p.min)),
            ("max",  "Max",        _fmt(p.max)),
            ("q25",  "Q25",        _fmt(p.q25)),
            ("q50",  "Médiane",    _fmt(p.q50)),
            ("q75",  "Q75",        _fmt(p.q75)),
        ]
    elif p.col_type in {"categorical", "boolean"}:
        rows.append(("jensen_shannon", "JS divergence", "0.000"))
        for val, freq in list(p.value_counts.items())[:3]:
            rows.append((f"cat__{val}", f"  {val}", f"{freq:.1%}"))
    elif p.col_type == "text":
        rows.append(("regex_compliance", "Conformité regex", "—"))
        rows.append(("avg_length", "Long. moy.",
                     f"{p.avg_length:.1f} car." if p.avg_length is not None else "—"))
    elif p.col_type == "datetime":
        rows.append(("dt_min", "Min", p.dt_min or "—"))
        rows.append(("dt_max", "Max", p.dt_max or "—"))
    return rows


def _synt_cell(key: str, p_synt: ColumnProfile | None, details: dict) -> str:
    NEUTRAL = "<td style='font-size:.8rem;padding:2px 6px;font-weight:500;'>{}</td>"
    EMPTY   = "<td style='font-size:.8rem;padding:2px 6px;color:#bbb;'>—</td>"

    if key in details and "note" not in details[key]:
        info    = details[key]
        raw     = info.get("synthetic")
        ok      = info.get("ok", True)
        val_str = f"{raw:.4g}" if isinstance(raw, float) else (str(raw) if raw is not None else "—")
        color   = COLOR_SUCCESS if ok else COLOR_DANGER
        icon    = "✓" if ok else "✗"
        return (
            f"<td style='font-size:.8rem;padding:2px 6px;"
            f"font-weight:500;color:{color};'>{val_str} {icon}</td>"
        )

    if p_synt is None:
        return EMPTY

    val: str | None = None
    if   key == "null_rate":  val = f"{p_synt.null_rate:.1%}"
    elif key == "mean"   and p_synt.mean  is not None: val = _fmt(p_synt.mean)
    elif key == "std"    and p_synt.std   is not None: val = _fmt(p_synt.std)
    elif key == "min"    and p_synt.min   is not None: val = _fmt(p_synt.min)
    elif key == "max"    and p_synt.max   is not None: val = _fmt(p_synt.max)
    elif key == "q25"    and p_synt.q25   is not None: val = _fmt(p_synt.q25)
    elif key == "q50"    and p_synt.q50   is not None: val = _fmt(p_synt.q50)
    elif key == "q75"    and p_synt.q75   is not None: val = _fmt(p_synt.q75)
    elif key == "avg_length" and p_synt.avg_length is not None:
        val = f"{p_synt.avg_length:.1f} car."
    elif key == "dt_min": val = p_synt.dt_min or "—"
    elif key == "dt_max": val = p_synt.dt_max or "—"
    elif key.startswith("cat__"):
        modal = key[5:]
        freq = p_synt.value_counts.get(modal)
        if freq is None:
            modal_norm = modal.strip().lower()
            for k, v in p_synt.value_counts.items():
                if str(k).strip().lower() == modal_norm:
                    freq = v
                    break
        if freq is not None:
            val = f"{freq:.1%}"

    if val is not None and val not in ("—", ""):
        return NEUTRAL.format(val)
    return EMPTY


def _render_comparison_table(p: ColumnProfile, cr: ColumnReport | None) -> None:
    details = cr.details if cr else {}
    p_synt  = cr.profile_synthetic if cr else None
    rows    = _profile_rows(p)
    header = (
        f"<tr style='font-size:.75rem;color:#aaa;border-bottom:1px solid #dde3e8;'>"
        f"<th style='padding:2px 6px;font-weight:400;text-align:left;'>Métrique</th>"
        f"<th style='padding:2px 6px;font-weight:400;text-align:left;'>Original</th>"
        f"<th style='padding:2px 6px;font-weight:400;text-align:left;'>Synthétique</th>"
        f"</tr>"
    )
    trs = []
    for key, label, orig_str in rows:
        sc = (
            "<td style='font-size:.8rem;padding:2px 6px;color:#bbb;'>—</td>"
            if cr is None
            else _synt_cell(key, p_synt, details)
        )
        trs.append(
            f"<tr>"
            f"<td style='color:#6c757d;font-size:.8rem;padding:2px 6px;'>{label}</td>"
            f"<td style='font-size:.8rem;padding:2px 6px;font-weight:500;'>{orig_str}</td>"
            f"{sc}"
            f"</tr>"
        )
    st.markdown(
        f"<table style='border-collapse:collapse;width:100%;'>"
        f"{header}{''.join(trs)}</table>",
        unsafe_allow_html=True,
    )


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


def _render_column_expanders(
    profiles: dict[str, ColumnProfile],
    col_reports: dict[str, ColumnReport] | None,
    regex_map: dict[str, str],
) -> None:
    for col, p in profiles.items():
        cr = col_reports.get(col) if col_reports else None
        expanded    = cr is not None and not cr.compliant
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
            _render_comparison_table(p, cr)

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
        page_title="Midara – Générateur de jeu de test",
        page_icon="🧪",
        layout="wide",
    )
    inject_styles()

    with st.sidebar:
        sidebar_app_logo()
        st.markdown(
            "<p style='font-size:.85rem;font-weight:600;margin-bottom:6px;'>📂 Fichier source</p>",
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "CSV · XLSX · Parquet",
            type=["csv", "xlsx", "xls", "parquet"],
            label_visibility="visible",
        )
        st.markdown("---")
        st.markdown(
            "<p style='font-size:.85rem;font-weight:600;margin-bottom:4px;'>Nombre de lignes à générer</p>",
            unsafe_allow_html=True,
        )
        n_rows = st.number_input(
            "Lignes", min_value=10, max_value=1_000_000, value=1000, step=100,
            label_visibility="collapsed",
        )
        st.markdown("---")
        with st.expander("⚙ Paramètres avancés", expanded=False):
            st.markdown(
                "<p style='font-size:.8rem;font-weight:600;margin-bottom:4px;'>Reproductibilité</p>",
                unsafe_allow_html=True,
            )
            seed = st.number_input("Seed", min_value=0, value=42)
            st.markdown(
                "<p style='font-size:.8rem;font-weight:600;margin:8px 0 4px;'>Tolérances de conformité</p>",
                unsafe_allow_html=True,
            )
            tolerance      = st.slider("Tolérance numérique (%)", 1, 20, 5) / 100
            js_threshold   = st.slider("Seuil Jensen-Shannon", 0.01, 0.20, 0.05, step=0.01)
            regex_min_rate = st.slider("Conformité regex min. (%)", 50, 100, 95) / 100
        sidebar_logo()

    st.markdown(
        f"<h3 style='color:{COLOR_PRIMARY};margin-bottom:.25rem;'>Midara</h3>"
        f"<p style='color:#6c757d;font-size:.9rem;margin-bottom:1.5rem;'>"
        f"Projet Anonyx · Générateur de jeu de test statistiquement conforme — "
        f"Chargez un fichier dans la barre latérale, puis lancez la génération.</p>",
        unsafe_allow_html=True,
    )

    if uploaded is None:
        alert("Déposez un fichier CSV, XLSX ou Parquet dans la barre latérale pour commencer.")
        return

    try:
        df_orig = load_file(uploaded, filename=uploaded.name)
    except Exception as e:
        alert(f"Erreur de chargement : {e}", "danger")
        return

    st.success(f"✓ {uploaded.name} — {df_orig.shape[0]} lignes × {df_orig.shape[1]} colonnes")
    with st.expander("Aperçu des données source", expanded=False):
        st.dataframe(df_orig.head(20), width='stretch')

    profiles = profile_dataframe(df_orig)

    if "regex_map" not in st.session_state:
        st.session_state["regex_map"] = {}
    regex_map: dict[str, str] = st.session_state["regex_map"]

    col_reports: dict[str, ColumnReport] | None = None
    if "report" in st.session_state:
        col_reports = {r.name: r for r in st.session_state["report"].column_reports}

    n_id   = sum(1 for p in profiles.values() if p.likely_identifier)
    n_yr   = sum(1 for p in profiles.values() if p.likely_year)
    n_ko   = sum(1 for cr in (col_reports or {}).values() if not cr.compliant)
    n_cols = len(profiles)
    status = f" · \u26a0 {n_ko} KO" if n_ko else (" · \u2713 tout OK" if col_reports else "")
    accordion_label = f"\u2460 Vue par colonne \u2014 {n_cols} colonnes{status}"

    section_header("① Vue par colonne", f"Profil · type inféré · résultat synthétique · regex — {n_cols} colonnes{status}")

    with st.expander("Détail des colonnes", expanded=True):
        if n_id:
            alert(
                f"\u26a0 {n_id} colonne(s) requalifi\u00e9e(s) en <strong>texte</strong> (identifiant probable) : "
                + ", ".join(f"<strong>{p.name}</strong>" for p in profiles.values() if p.likely_identifier),
                "warning",
            )
        if n_yr:
            alert(
                f"\U0001f4c5 {n_yr} colonne(s) requalifi\u00e9e(s) en <strong>cat\u00e9goriel</strong> (ann\u00e9e probable) : "
                + ", ".join(f"<strong>{p.name}</strong>" for p in profiles.values() if p.likely_year),
                "info",
            )
        _render_column_expanders(profiles, col_reports, regex_map)

    section_header("② Corrélations sensibles", "|r| > 0.7 — sélectionnez les paires à contraindre")
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

    section_header("③ Génération")
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
                st.session_state["tolerance"]         = tolerance
                st.rerun()
            except Exception as e:
                alert(f"Erreur lors de la génération : {e}", "danger")
                return

    if "report" not in st.session_state:
        return

    report    = st.session_state["report"]
    df_synt   = st.session_state["df_synt"]
    tolerance = st.session_state.get("tolerance", 0.05)

    # ── ④ Qualité du jeu de test ─────────────────────────────────────────────
    section_header("④ Qualité du jeu de test", "Score de conformité global · colonnes · corrélations")

    n_ko_rep = sum(1 for r in report.column_reports if not r.compliant)
    n_ok_rep = len(report.column_reports) - n_ko_rep
    n_cor_ko = sum(1 for r in report.correlation_reports if not r.compliant)
    n_cor_ok = len(report.correlation_reports) - n_cor_ko

    progress_badge("Score global de conformité", report.global_score)

    c1, c2, c3, c4 = st.columns(4)

    def _metric_card(col, label: str, value: str, sub: str, ok: bool) -> None:
        color = COLOR_SUCCESS if ok else COLOR_DANGER
        col.markdown(
            f"<div style='background:#fff;border-left:4px solid {color};border-radius:6px;"
            f"padding:10px 14px;box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:4px;'>"
            f"<div style='font-size:.75rem;color:#6c757d;margin-bottom:2px;'>{label}</div>"
            f"<div style='font-size:1.35rem;font-weight:700;color:{color};'>{value}</div>"
            f"<div style='font-size:.75rem;color:#aaa;margin-top:2px;'>{sub}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    _metric_card(c1, "Score global",
                 f"{int(report.global_score * 100)} %",
                 "conformité synthétique", report.global_score >= 0.8)
    _metric_card(c2, "Colonnes conformes",
                 f"{n_ok_rep} / {len(report.column_reports)}",
                 f"{n_ko_rep} KO" if n_ko_rep else "toutes OK", n_ko_rep == 0)
    _metric_card(c3, "Corrélations OK",
                 f"{n_cor_ok} / {len(report.correlation_reports)}" if report.correlation_reports else "—",
                 f"{n_cor_ko} hors tolérance" if n_cor_ko else ("toutes OK" if report.correlation_reports else "aucune contrainte"),
                 n_cor_ko == 0)
    _metric_card(c4, "Lignes générées",
                 f"{len(df_synt):,}".replace(",", " "),
                 "jeu synthétique", True)

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

    if n_ko_rep:
        alert(f"{n_ko_rep} colonne(s) non conforme(s) — détail dans le bloc ① ci-dessus.", "warning")
        ko_rows = "".join(
            f"<tr><td style='padding:5px 10px;font-size:.85rem;'>{r.name}</td>"
            f"<td style='padding:5px 10px;'>"
            f"<span style='background:#6f42c1;color:#fff;padding:1px 6px;border-radius:3px;font-size:.72rem;'>{r.col_type}</span></td>"
            f"<td style='padding:5px 10px;font-size:.85rem;color:{COLOR_DANGER};'>{r.reason}</td></tr>"
            for r in report.column_reports if not r.compliant
        )
        st.markdown(
            f"<table style='border-collapse:collapse;width:100%;margin-top:6px;'>"
            f"<thead><tr>"
            f"<th style='background:{COLOR_PRIMARY};color:#fff;padding:6px 10px;font-size:.8rem;text-align:left;'>Colonne</th>"
            f"<th style='background:{COLOR_PRIMARY};color:#fff;padding:6px 10px;font-size:.8rem;text-align:left;'>Type</th>"
            f"<th style='background:{COLOR_PRIMARY};color:#fff;padding:6px 10px;font-size:.8rem;text-align:left;'>Motif KO</th>"
            f"</tr></thead><tbody>{ko_rows}</tbody></table>",
            unsafe_allow_html=True,
        )
    else:
        alert("Toutes les colonnes sont conformes.", "success")

    if report.correlation_reports:
        st.markdown(
            "<p style='font-size:.85rem;font-weight:600;margin-top:14px;margin-bottom:4px;color:#444;'>"
            "Corrélations contraintes</p>",
            unsafe_allow_html=True,
        )
        _render_correlation_heatmap(report.correlation_reports, tolerance)

    with st.expander("Aperçu du jeu synthétique", expanded=False):
        st.dataframe(df_synt.head(20), width='stretch')

    # ── ⑤ Rapport détaillé ───────────────────────────────────────────────────
    section_header("⑤ Rapport détaillé", "Conformité colonne par colonne")

    with st.expander("Voir le rapport complet", expanded=False):
        progress_badge("Score global", report.global_score)
        for r in report.column_reports:
            ok_icon = f'<b style="color:{COLOR_SUCCESS}">✓</b>' if r.compliant else f'<b style="color:{COLOR_DANGER}">✗</b>'
            reason  = f' &nbsp;— <span style="color:{COLOR_DANGER};font-size:.8rem;">{r.reason}</span>' if not r.compliant else ""
            st.markdown(
                f"<span style='font-size:.85rem;'>{ok_icon} &nbsp;<strong>{r.name}</strong>"
                f" &nbsp;<span style='color:#6c757d;font-size:.8rem;'>[{r.col_type}]</span>{reason}</span>",
                unsafe_allow_html=True,
            )

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
            data=export_bytes, file_name=f"midara_synthetic.{export_fmt}",
            mime=mime_map[export_fmt], width='stretch',
        )
    with col_b:
        st.download_button(
            label="⬇ Télécharger le rapport (.html)",
            data=_report_html(report).encode(),
            file_name="midara_report.html", mime="text/html", width='stretch',
        )
