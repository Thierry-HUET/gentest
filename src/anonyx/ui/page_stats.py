"""
page_stats.py – Page Statistiques Midara.

Contenu :
  ① Vue par colonne — profil original
  ② Corrélations sensibles (sélection des paires à contraindre)
  ③ Vue par colonne enrichie — original + synthétique
  ④ Qualité du jeu de test (métriques, tableau KO, heatmap corrélations)
  ⑤ Associations bivariées
  ⑥ Rapport détaillé colonne par colonne
"""
from __future__ import annotations

import streamlit as st

from anonyx.core.correlations import detect_sensitive_pairs, sensitive_only, CorrelationPair
from anonyx.core.profiler import ColumnProfile
from anonyx.core.validator import ColumnReport, CorrelationReport, ConformityReport
from anonyx.core.bivariate import BivariateResult
from anonyx.core.logger import get_logger
from anonyx.ui.components import (
    alert,
    progress_badge,
    section_header,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_DANGER,
    COLOR_WARNING,
    COLOR_LIGHT,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Utilitaires de formatage
# ---------------------------------------------------------------------------
def _fmt(v: object) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def _profile_rows(p: ColumnProfile) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = [("null_rate", "Taux nuls", f"{p.null_rate:.2%}")]
    if p.col_type == "numeric":
        rows += [
            ("mean", "Moyenne", _fmt(p.mean)),
            ("std", "Écart-type", _fmt(p.std)),
            ("min", "Min", _fmt(p.min)),
            ("max", "Max", _fmt(p.max)),
            ("q25", "Q25", _fmt(p.q25)),
            ("q50", "Médiane", _fmt(p.q50)),
            ("q75", "Q75", _fmt(p.q75)),
        ]
    elif p.col_type in {"categorical", "boolean"}:
        rows.append(("jensen_shannon", "JS divergence", "0.000"))
        if p.null_rate < 1.0:
            for val, freq in list(p.value_counts.items())[:3]:
                rows.append((f"cat__{val}", f"  {val}", f"{freq:.2%}"))
        else:
            rows.append(("_all_null", "  (toutes nulles)", "—"))
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
    ZERO    = "<td style='font-size:.8rem;padding:2px 6px;color:#bbb;font-style:italic;'>0.00%</td>"

    if key in details and "note" not in details[key]:
        info    = details[key]
        raw     = info.get("synthetic")
        ok      = info.get("ok", True)
        val_str = f"{raw:.4g}" if isinstance(raw, float) else (str(raw) if raw is not None else "—")
        color   = COLOR_SUCCESS if ok else COLOR_DANGER
        icon    = "✓" if ok else "✗"
        return (f"<td style='font-size:.8rem;padding:2px 6px;"
                f"font-weight:500;color:{color};'>{val_str} {icon}</td>")

    if p_synt is None:
        return EMPTY

    val: str | None = None
    if   key == "null_rate":   val = f"{p_synt.null_rate:.2%}"
    elif key == "mean"    and p_synt.mean   is not None: val = _fmt(p_synt.mean)
    elif key == "std"     and p_synt.std    is not None: val = _fmt(p_synt.std)
    elif key == "min"     and p_synt.min    is not None: val = _fmt(p_synt.min)
    elif key == "max"     and p_synt.max    is not None: val = _fmt(p_synt.max)
    elif key == "q25"     and p_synt.q25    is not None: val = _fmt(p_synt.q25)
    elif key == "q50"     and p_synt.q50    is not None: val = _fmt(p_synt.q50)
    elif key == "q75"     and p_synt.q75    is not None: val = _fmt(p_synt.q75)
    elif key == "avg_length" and p_synt.avg_length is not None:
        val = f"{p_synt.avg_length:.1f} car."
    elif key == "dt_min":  val = p_synt.dt_min or "—"
    elif key == "dt_max":  val = p_synt.dt_max or "—"
    elif key == "_all_null": val = "—"
    elif key.startswith("cat__"):
        modal = key[5:]
        freq  = p_synt.value_counts.get(modal)
        if freq is None:
            modal_norm = modal.strip().lower()
            for k, v in p_synt.value_counts.items():
                if str(k).strip().lower() == modal_norm:
                    freq = v
                    break
        if freq is not None:
            val = f"{freq:.2%}"
        else:
            return ZERO

    if val is not None and val not in ("—", ""):
        return NEUTRAL.format(val)
    return EMPTY


# ---------------------------------------------------------------------------
# Tableau comparatif par colonne
# ---------------------------------------------------------------------------
def _render_comparison_table(p: ColumnProfile, cr: ColumnReport | None) -> None:
    details = cr.details if cr else {}
    p_synt  = cr.profile_synthetic if cr else None
    rows    = _profile_rows(p)
    header  = (
        "<tr style='font-size:.75rem;color:#aaa;border-bottom:1px solid #dde3e8;'>"
        "<th style='padding:2px 6px;font-weight:400;text-align:left;'>Métrique</th>"
        "<th style='padding:2px 6px;font-weight:400;text-align:left;'>Original</th>"
        "<th style='padding:2px 6px;font-weight:400;text-align:left;'>Synthétique</th>"
        "</tr>"
    )
    trs = []
    for key, label, orig_str in rows:
        sc = ("<td style='font-size:.8rem;padding:2px 6px;color:#bbb;'>—</td>"
              if cr is None else _synt_cell(key, p_synt, details))
        trs.append(
            f"<tr><td style='color:#6c757d;font-size:.8rem;padding:2px 6px;'>{label}</td>"
            f"<td style='font-size:.8rem;padding:2px 6px;font-weight:500;'>{orig_str}</td>"
            f"{sc}</tr>"
        )
    st.markdown(
        f"<table style='border-collapse:collapse;width:100%;'>"
        f"{header}{''.join(trs)}</table>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Expanders par colonne
# ---------------------------------------------------------------------------
def _col_expander_title(p: ColumnProfile, cr: ColumnReport | None) -> str:
    type_color = {
        "numeric": COLOR_PRIMARY, "categorical": "#6f42c1", "boolean": "#0d6efd",
        "text": "#20c997", "datetime": "#fd7e14", "unknown": "#6c757d",
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
        parts.append(
            "<span class='gt-ok'>✓ OK</span>"
            if cr.compliant
            else f"<span class='gt-ko'>✗ KO — {cr.reason}</span>"
        )
    return "  ".join(parts)


def _render_column_expanders(
    profiles: dict[str, ColumnProfile],
    col_reports: dict[str, ColumnReport] | None,
    regex_map: dict[str, str],
    key_prefix: str = "",
) -> None:
    for col, p in profiles.items():
        cr          = col_reports.get(col) if col_reports else None
        expanded    = cr is not None and not cr.compliant
        status_icon = "" if cr is None else ("✓" if cr.compliant else "✗")
        flags       = (["⚠ id"] if p.likely_identifier else []) + (["📅 année"] if p.likely_year else [])
        flag_str    = ("  " + "  ".join(flags)) if flags else ""
        plain_title = f"{status_icon}  {col}  [{p.col_type}{flag_str}]"

        with st.expander(plain_title, expanded=expanded):
            st.markdown(
                f"<div style='margin-bottom:8px;'>{_col_expander_title(p, cr)}</div>",
                unsafe_allow_html=True,
            )
            if p.likely_identifier:
                alert(
                    "⚠ Identifiant probable — traité comme <strong>texte</strong> "
                    "(rééchantillonnage). Définissez un pattern regex ci-dessous si besoin.",
                    "warning",
                )
            if p.likely_year:
                alert(
                    "📅 Année probable — traité comme <strong>catégoriel</strong> "
                    "(distribution observée préservée, valeurs entières restituées).",
                    "info",
                )
            _render_comparison_table(p, cr)
            if p.col_type == "text":
                st.markdown("<hr style='margin:8px 0;border-color:#dde3e8;'>", unsafe_allow_html=True)
                pat = st.text_input(
                    "Pattern regex (optionnel)",
                    value=regex_map.get(col, ""),
                    placeholder=r"ex: [A-Z]{2}\d{4}",
                    key=f"{key_prefix}regex_{col}",
                )
                if pat.strip():
                    regex_map[col] = pat.strip()
                elif col in regex_map:
                    del regex_map[col]


# ---------------------------------------------------------------------------
# Heatmaps
# ---------------------------------------------------------------------------
def _render_bivariate_heatmap(result: BivariateResult) -> None:
    cols = result.columns
    n    = len(cols)
    if n < 2:
        alert("Moins de 2 colonnes bivariées retenues après filtrage spectral.")
        return

    CELL  = 80
    LABEL = 110
    PAD   = 4
    total_w = LABEL + n * (CELL + PAD)
    total_h = LABEL + n * (CELL + PAD)

    def _color(v: float, is_synt: bool = False) -> str:
        v = max(0.0, min(1.0, v))
        if is_synt:
            r = int(255 - v * (255 - 230))
            g = int(255 - v * (255 - 100))
            b = int(255 - v * 255)
        else:
            r = int(255 - v * (255 - 0))
            g = int(255 - v * (255 - 77))
            b = int(255 - v * (255 - 153))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _tc(v: float) -> str:
        return "#fff" if v > 0.45 else "#333"

    TYPE_LABEL = {"num×num": "r²", "cat×cat": "V", "η²": "η²", "num×cat": "η²"}
    cells = []

    for i, col in enumerate(cols):
        x     = LABEL + i * (CELL + PAD) + CELL // 2
        short = col if len(col) <= 14 else col[:12] + "…"
        cells.append(
            f'<text x="{x}" y="{LABEL-6}" text-anchor="middle" '
            f'font-size="9" font-family="Segoe UI,sans-serif" fill="#444">{short}</text>'
        )
        yl = LABEL + i * (CELL + PAD) + CELL // 2 + 4
        cells.append(
            f'<text x="{LABEL-6}" y="{yl}" text-anchor="end" '
            f'font-size="9" font-family="Segoe UI,sans-serif" fill="#444">{short}</text>'
        )

    for i in range(n):
        for j in range(n):
            x = LABEL + j * (CELL + PAD)
            y = LABEL + i * (CELL + PAD)
            if i == j:
                cells.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="4" fill="#f0f4f8"/>')
                cells.append(
                    f'<text x="{x+CELL//2}" y="{y+CELL//2+4}" text-anchor="middle" '
                    f'font-size="8" font-family="Segoe UI,sans-serif" fill="#888">1.000</text>'
                )
            elif i < j:
                v  = result.matrix_orig[i, j]
                bg = _color(v)
                tc = _tc(v)
                metric = TYPE_LABEL.get(result.pair_types.get((cols[i], cols[j]), ""), "")
                cells.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="4" fill="{bg}"/>')
                cells.append(
                    f'<text x="{x+CELL//2}" y="{y+CELL//2}" text-anchor="middle" '
                    f'font-size="11" font-family="Segoe UI,sans-serif" font-weight="600" fill="{tc}">{v:.3f}</text>'
                )
                cells.append(
                    f'<text x="{x+CELL//2}" y="{y+CELL//2+13}" text-anchor="middle" '
                    f'font-size="8" font-family="Segoe UI,sans-serif" fill="{tc}">{metric}</text>'
                )
            else:
                if result.matrix_synt is not None:
                    v     = result.matrix_synt[i, j]
                    delta = abs(v - result.matrix_orig[i, j])
                    bg    = _color(v, is_synt=True)
                    tc    = _tc(v)
                    cells.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="4" fill="{bg}"/>')
                    cells.append(
                        f'<text x="{x+CELL//2}" y="{y+CELL//2}" text-anchor="middle" '
                        f'font-size="11" font-family="Segoe UI,sans-serif" font-weight="600" fill="{tc}">{v:.3f}</text>'
                    )
                    cells.append(
                        f'<text x="{x+CELL//2}" y="{y+CELL//2+13}" text-anchor="middle" '
                        f'font-size="8" font-family="Segoe UI,sans-serif" fill="{tc}">Δ {delta:.3f}</text>'
                    )
                else:
                    cells.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="4" fill="#f8f9fa"/>')
                    cells.append(
                        f'<text x="{x+CELL//2}" y="{y+CELL//2+4}" text-anchor="middle" '
                        f'font-size="9" font-family="Segoe UI,sans-serif" fill="#ccc">—</text>'
                    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" '
        f'width="{total_w}" height="{total_h}">' + "".join(cells) + "</svg>"
    )
    has_synt    = result.matrix_synt is not None
    legend_orig = (
        '<span style="display:inline-block;width:12px;height:12px;background:#004d99;'
        'border-radius:2px;margin-right:4px;"></span>Original (bleu)'
    )
    legend_synt = (
        '<span style="display:inline-block;width:12px;height:12px;background:#e66400;'
        'border-radius:2px;margin-right:4px;"></span>Synthétique (orange)'
        if has_synt else ""
    )
    metric_note = "r² = Pearson² (num×num) · V = Cramér (cat×cat) · η² = rapport de corrélation (num×cat)"
    html_content = (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        f'body{{margin:0;padding:4px;background:transparent;font-family:"Segoe UI",sans-serif;overflow:auto;}}'
        f'.legend{{font-size:11px;color:#666;margin-top:8px;line-height:1.8;}}'
        f'</style></head><body><div style="overflow-x:auto;">{svg}</div>'
        f'<div class="legend">{legend_orig}'
        + (f' &nbsp;&nbsp; {legend_synt}' if has_synt else '')
        + f'<br><span style="color:#999;">{metric_note}</span>'
        + f'<br><span style="color:#999;">'
        + f'{result.n_significant} VP > 1 (Kaiser) · {len(cols)} colonne(s) retenue(s)</span>'
        + '</div></body></html>'
    )
    st.html(html_content)


def _lerp_color(t: float) -> str:
    t = max(0.0, min(1.0, t))
    return f"#{int(25+t*(192-25)):02x}{int(135+t*(57-135)):02x}{int(84+t*(43-84)):02x}"


def _render_correlation_heatmap(reports: list[CorrelationReport], tolerance: float) -> None:
    n = len(reports)
    if n == 0:
        return
    cell_w, cell_h, pad = 120, 64, 8
    total_w = n * (cell_w + pad) - pad
    total_h = cell_h + 22 + 6
    delta_max = tolerance * 2
    cells = []
    for i, r in enumerate(reports):
        x     = i * (cell_w + pad)
        t     = min(1.0, r.delta / delta_max) if delta_max > 0 else (0.0 if r.compliant else 1.0)
        color = _lerp_color(t)
        icon  = "✓" if r.compliant else "✗"
        label = (r.col_a + " ↔ " + r.col_b)[:20] + ("…" if len(r.col_a + r.col_b) > 18 else "")
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
    st.html(html_content)


# ---------------------------------------------------------------------------
# Sections principales
# ---------------------------------------------------------------------------
def _render_section_profiles(profiles, col_reports, regex_map, n_id, n_yr, key_prefix) -> None:
    with st.expander("Détail des colonnes", expanded=False):
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
        _render_column_expanders(profiles, col_reports, regex_map, key_prefix=key_prefix)


def _render_section_correlations(df_orig, profiles) -> None:
    all_pairs  = detect_sensitive_pairs(df_orig, profiles)
    sens_pairs = sensitive_only(all_pairs)
    if not sens_pairs:
        alert("Aucune corrélation sensible détectée (|r| > 0,7).")
        return
    pair_labels = [
        f"{p.col_a} ↔ {p.col_b}  ({p.method}, r={p.coefficient:.2f})"
        for p in sens_pairs
    ]
    st.multiselect(
        "Paires contraintes lors de la génération",
        options=pair_labels,
        default=pair_labels,
        disabled=True,
        help="La sélection des paires est gérée automatiquement (toutes contraintes). "
             "Cette vue est informative.",
    )


def _render_section_quality(report: ConformityReport, df_synt, tolerance: float) -> None:
    n_ko     = sum(1 for r in report.column_reports if not r.compliant)
    n_ok     = len(report.column_reports) - n_ko
    n_cor_ko = sum(1 for r in report.correlation_reports if not r.compliant)
    n_cor_ok = len(report.correlation_reports) - n_cor_ko

    progress_badge("Score global de conformité", report.global_score)

    c1, c2, c3, c4 = st.columns(4)

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

    _card(c1, "Score global", f"{int(report.global_score * 100)} %",
          "conformité synthétique", report.global_score >= 0.8)
    _card(c2, "Colonnes conformes",
          f"{n_ok} / {len(report.column_reports)}",
          f"{n_ko} KO" if n_ko else "toutes OK", n_ko == 0)
    _card(c3, "Corrélations OK",
          f"{n_cor_ok} / {len(report.correlation_reports)}"
          if report.correlation_reports else "—",
          f"{n_cor_ko} hors tolérance" if n_cor_ko else (
              "toutes OK" if report.correlation_reports else "aucune contrainte"),
          n_cor_ko == 0)
    _card(c4, "Lignes générées",
          f"{len(df_synt):,}".replace(",", "\u202f"),
          "jeu synthétique", True)

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

    if n_ko:
        alert(f"{n_ko} colonne(s) non conforme(s).", "warning")
        ko_rows = "".join(
            f"<tr><td style='padding:5px 10px;font-size:.85rem;'>{r.name}</td>"
            f"<td style='padding:5px 10px;'>"
            f"<span style='background:#6f42c1;color:#fff;padding:1px 6px;border-radius:3px;font-size:.72rem;'>"
            f"{r.col_type}</span></td>"
            f"<td style='padding:5px 10px;font-size:.85rem;color:{COLOR_DANGER};'>{r.reason}</td></tr>"
            for r in report.column_reports if not r.compliant
        )
        st.markdown(
            f"<table style='border-collapse:collapse;width:100%;margin-top:6px;'><thead><tr>"
            f"<th style='background:{COLOR_PRIMARY};color:#fff;padding:6px 10px;"
            f"font-size:.8rem;text-align:left;'>Colonne</th>"
            f"<th style='background:{COLOR_PRIMARY};color:#fff;padding:6px 10px;"
            f"font-size:.8rem;text-align:left;'>Type</th>"
            f"<th style='background:{COLOR_PRIMARY};color:#fff;padding:6px 10px;"
            f"font-size:.8rem;text-align:left;'>Motif KO</th>"
            f"</tr></thead><tbody>{ko_rows}</tbody></table>",
            unsafe_allow_html=True,
        )
    else:
        alert("Toutes les colonnes sont conformes.", "success")

    if report.correlation_reports:
        st.markdown(
            "<p style='font-size:.85rem;font-weight:600;margin-top:14px;"
            "margin-bottom:4px;color:#444;'>Corrélations contraintes</p>",
            unsafe_allow_html=True,
        )
        _render_correlation_heatmap(report.correlation_reports, tolerance)

    with st.expander("Aperçu du jeu synthétique", expanded=False):
        st.dataframe(df_synt.head(20), use_container_width=True)


def _render_section_detailed_report(report: ConformityReport) -> None:
    with st.expander("Voir le rapport complet", expanded=False):
        progress_badge("Score global", report.global_score)
        for r in report.column_reports:
            ok_icon = (
                f'<b style="color:{COLOR_SUCCESS}">✓</b>'
                if r.compliant
                else f'<b style="color:{COLOR_DANGER}">✗</b>'
            )
            reason = (
                f' &nbsp;— <span style="color:{COLOR_DANGER};font-size:.8rem;">{r.reason}</span>'
                if not r.compliant else ""
            )
            st.markdown(
                f"<span style='font-size:.85rem;'>{ok_icon} &nbsp;<strong>{r.name}</strong>"
                f" &nbsp;<span style='color:#6c757d;font-size:.8rem;'>[{r.col_type}]</span>"
                f"{reason}</span>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Point d'entrée de la page
# ---------------------------------------------------------------------------
def render() -> None:
    """Appelé par layout.py. Lit l'état depuis st.session_state."""
    profiles = st.session_state.get("profiles")
    report   = st.session_state.get("report")
    df_synt  = st.session_state.get("df_synt")
    df_orig  = st.session_state.get("_df_orig_ref")  # référence stockée par layout
    tolerance = st.session_state.get("tolerance", 0.05)

    if profiles is None or df_orig is None:
        alert(
            "Aucune donnée disponible. Chargez un fichier sur la page "
            "<strong>Accueil</strong> pour accéder aux statistiques.",
        )
        return

    regex_map: dict = st.session_state.get("regex_map", {})
    n_id  = sum(1 for p in profiles.values() if p.likely_identifier)
    n_yr  = sum(1 for p in profiles.values() if p.likely_year)
    n_cols = len(profiles)

    # ① Profil original
    col_reports = {r.name: r for r in report.column_reports} if report else None
    n_ko        = sum(1 for cr in col_reports.values() if not cr.compliant) if col_reports else 0
    status      = f" · ⚠ {n_ko} KO" if n_ko else (" · ✓ tout OK" if report else "")
    section_header(
        "① Vue par colonne",
        f"Profil · type inféré · regex — {n_cols} colonnes{status}",
    )
    _render_section_profiles(profiles, col_reports, regex_map, n_id, n_yr, key_prefix="stats_")

    # ② Corrélations sensibles
    section_header("② Corrélations sensibles", "|r| > 0,7 — paires contraintes à la génération")
    _render_section_correlations(df_orig, profiles)

    if report is None or df_synt is None:
        alert("Lancez la génération depuis la page <strong>Accueil</strong> pour voir les résultats.", "info")
        return

    # ③ Qualité du jeu de test
    section_header("③ Qualité du jeu de test", "Score de conformité · colonnes · corrélations")
    _render_section_quality(report, df_synt, tolerance)

    # ④ Associations bivariées
    biv = st.session_state.get("bivariate") or st.session_state.get("bivariate_orig")
    if biv is not None:
        section_header(
            "④ Associations bivariées",
            f"Filtrage spectral Kaiser (λ>1) · "
            f"{biv.n_significant} VP significative(s) · {len(biv.columns)} colonne(s) retenue(s)",
        )
        _render_bivariate_heatmap(biv)

    # ⑤ Rapport détaillé
    section_header("⑤ Rapport détaillé", "Conformité colonne par colonne")
    _render_section_detailed_report(report)
