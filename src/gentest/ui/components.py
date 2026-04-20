"""
components.py – Composants UI réutilisables (CSS personnalisé, sans Bootstrap).

Streamlit isole son rendu dans un DOM React. Tous les styles sont donc
définis en CSS inline ou via des classes gentest-* injectées dans <style>.
Les composants interactifs complexes (accordéon) utilisent
st.components.v1.html() dans un iframe avec CSS autonome.
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# Palette projet
# ---------------------------------------------------------------------------
COLOR_PRIMARY   = "#006699"
COLOR_SECONDARY = "#004d73"
COLOR_ACCENT    = "#33aadd"
COLOR_LIGHT     = "#e8f4f8"
COLOR_SUCCESS   = "#198754"
COLOR_WARNING   = "#e6a817"
COLOR_DANGER    = "#c0392b"

# ---------------------------------------------------------------------------
# CSS global injecté une seule fois au démarrage
# ---------------------------------------------------------------------------
_GLOBAL_CSS = f"""
<style>
  /* ---- Police ---- */
  @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;600;700&display=swap');
  html, body, [class*="css"], .stApp {{
      font-family: 'Avenir', 'Nunito', 'Segoe UI', sans-serif !important;
  }}

  /* ---- Layout ---- */
  .stApp {{ background-color: #f5f9fc !important; }}
  .block-container {{ padding-top: 1.5rem !important; max-width: 1200px; }}

  /* ---- Sidebar ---- */
  section[data-testid="stSidebar"] > div:first-child {{
      background-color: {COLOR_SECONDARY} !important;
  }}
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span,
  section[data-testid="stSidebar"] div {{
      color: #ffffff !important;
  }}

  /* ---- Bouton primaire ---- */
  .stButton > button[kind="primary"] {{
      background-color: {COLOR_PRIMARY} !important;
      border: none !important;
      color: #fff !important;
      font-weight: 600;
      border-radius: 6px;
  }}
  .stButton > button[kind="primary"]:hover {{
      background-color: {COLOR_SECONDARY} !important;
  }}

  /* ---- Badges conformité ---- */
  .gt-ok {{
      background: {COLOR_SUCCESS};
      color: #fff;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: .75rem;
      font-weight: 600;
  }}
  .gt-ko {{
      background: {COLOR_DANGER};
      color: #fff;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: .75rem;
      font-weight: 600;
  }}
  .gt-badge {{
      background: {COLOR_PRIMARY};
      color: #fff;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: .75rem;
      font-weight: 600;
  }}

  /* ---- Tables ---- */
  .gt-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: .85rem;
      margin-bottom: .75rem;
  }}
  .gt-table th {{
      background: {COLOR_PRIMARY};
      color: #fff;
      padding: 7px 10px;
      text-align: left;
      font-weight: 600;
      font-size: .82rem;
  }}
  .gt-table td {{
      padding: 6px 10px;
      border-bottom: 1px solid #dde3e8;
      vertical-align: middle;
  }}
  .gt-table tr:hover td {{
      background: {COLOR_LIGHT};
  }}

  /* ---- Barre de progression ---- */
  .gt-progress-wrap {{ margin-bottom: 1.2rem; }}
  .gt-progress-header {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 5px;
      font-weight: 600;
  }}
  .gt-progress-track {{
      background: #dde3e8;
      border-radius: 6px;
      height: 13px;
      overflow: hidden;
  }}
  .gt-progress-fill {{
      height: 100%;
      border-radius: 6px;
      transition: width .4s ease;
  }}

  /* ---- Section header ---- */
  .gt-section {{
      border-bottom: 2px solid {COLOR_PRIMARY};
      padding-bottom: 5px;
      margin-top: 1.6rem;
      margin-bottom: .9rem;
  }}
  .gt-section h5 {{
      color: {COLOR_PRIMARY};
      font-weight: 700;
      margin: 0 0 2px 0;
      font-size: 1rem;
  }}
  .gt-section p {{
      color: #6c757d;
      font-size: .85rem;
      margin: 0;
  }}

  /* ---- Alertes ---- */
  .gt-alert {{
      padding: 8px 14px;
      border-radius: 6px;
      font-size: .9rem;
      margin-bottom: 10px;
      border-left: 4px solid;
  }}
  .gt-alert-info    {{ background:#dff0fa; color:#0c5174; border-color:#006699; }}
  .gt-alert-success {{ background:#d4edda; color:#155724; border-color:#198754; }}
  .gt-alert-warning {{ background:#fff3cd; color:#7a5c00; border-color:#e6a817; }}
  .gt-alert-danger  {{ background:#fde8e8; color:#7b1d1d; border-color:#c0392b; }}

  /* ---- Card ---- */
  .gt-card {{
      background: #fff;
      border-left: 4px solid {COLOR_PRIMARY};
      border-radius: 6px;
      padding: 12px 16px;
      margin-bottom: 12px;
      box-shadow: 0 1px 4px rgba(0,0,0,.06);
  }}
  .gt-card-title {{
      font-weight: 600;
      color: {COLOR_PRIMARY};
      margin-bottom: 4px;
      font-size: .9rem;
  }}
</style>
"""


def inject_styles() -> None:
    """Injecte le CSS global une seule fois."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Composants génériques
# ---------------------------------------------------------------------------

def card(title: str, body: str) -> None:
    st.markdown(
        f'<div class="gt-card"><div class="gt-card-title">{title}</div>'
        f'<div style="font-size:.9rem;">{body}</div></div>',
        unsafe_allow_html=True,
    )


def progress_badge(label: str, score: float) -> None:
    pct = int(score * 100)
    color = COLOR_SUCCESS if pct >= 80 else (COLOR_WARNING if pct >= 60 else COLOR_DANGER)
    st.markdown(
        f"""
        <div class="gt-progress-wrap">
          <div class="gt-progress-header">
            <span>{label}</span>
            <span style="color:{color};">{pct} %</span>
          </div>
          <div class="gt-progress-track">
            <div class="gt-progress-fill" style="width:{pct}%; background:{color};"></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert(message: str, level: str = "info") -> None:
    """level : 'info' | 'success' | 'warning' | 'danger'"""
    st.markdown(
        f'<div class="gt-alert gt-alert-{level}">{message}</div>',
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f'<div class="gt-section"><h5>{title}</h5>{sub}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Accordéon (iframe autonome, CSS inline sans dépendance externe)
# ---------------------------------------------------------------------------
_ACC_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: 'Segoe UI', sans-serif;
    background: transparent;
    padding: 2px;
}}
.acc-item {{
    border: 1px solid #dde3e8;
    border-radius: 6px;
    margin-bottom: 6px;
    overflow: hidden;
}}
.acc-header {{
    width: 100%;
    background: #fff;
    border: none;
    text-align: left;
    padding: 10px 14px;
    font-size: .88rem;
    font-weight: 600;
    color: {COLOR_PRIMARY};
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: background .15s;
}}
.acc-header:hover {{ background: {COLOR_LIGHT}; }}
.acc-header.open  {{ background: {COLOR_LIGHT}; border-bottom: 1px solid #dde3e8; }}
.acc-chevron {{ font-size: .75rem; transition: transform .2s; }}
.acc-header.open .acc-chevron {{ transform: rotate(180deg); }}
.acc-body {{
    display: none;
    padding: 10px 14px;
    font-size: .84rem;
    color: #333;
    background: #fafcfd;
    line-height: 1.5;
}}
.acc-body.open {{ display: block; }}
"""

_ACC_JS = """
document.querySelectorAll('.acc-header').forEach(btn => {
    btn.addEventListener('click', () => {
        const body = btn.nextElementSibling;
        const isOpen = btn.classList.contains('open');
        // Ferme tous
        document.querySelectorAll('.acc-header').forEach(b => {
            b.classList.remove('open');
            b.nextElementSibling.classList.remove('open');
        });
        // Ouvre le cliqué si était fermé
        if (!isOpen) {
            btn.classList.add('open');
            body.classList.add('open');
        }
    });
});
// Ouvre le premier par défaut
const first = document.querySelector('.acc-header');
if (first) { first.classList.add('open'); first.nextElementSibling.classList.add('open'); }
"""


def accordion(items: list[tuple[str, str]], accordion_id: str = "acc") -> None:
    """
    Affiche un accordéon dans un iframe autonome (CSS + JS inline).

    Parameters
    ----------
    items        : liste de (titre, contenu_html)
    accordion_id : non utilisé, conservé pour compatibilité d'interface
    """
    items_html = "".join(
        f'<div class="acc-item">'
        f'<button class="acc-header">{title} <span class="acc-chevron">▼</span></button>'
        f'<div class="acc-body">{body}</div>'
        f'</div>'
        for title, body in items
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>{_ACC_CSS}</style></head>
    <body>
      <div id="accordion">{items_html}</div>
      <script>{_ACC_JS}</script>
    </body></html>"""

    height = 46 * len(items) + 150
    components.html(html, height=height, scrolling=False)
