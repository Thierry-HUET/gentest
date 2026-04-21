"""
components.py – Composants UI réutilisables (CSS personnalisé, sans dépendance externe).
"""
from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

import streamlit as st

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
# Logo (src/static/Logo_complet.png)
# ---------------------------------------------------------------------------
_LOGO_PATH    = Path(__file__).parent.parent.parent / "static" / "Logo_complet.png"
_VERSION_PATH = Path(__file__).parent.parent.parent.parent / "VERSION"


def _load_logo_b64() -> str | None:
    try:
        return base64.b64encode(_LOGO_PATH.read_bytes()).decode()
    except FileNotFoundError:
        return None


def _load_version() -> str:
    try:
        return _VERSION_PATH.read_text().strip()
    except FileNotFoundError:
        return "—"


_LOGO_B64 = _load_logo_b64()
_VERSION  = _load_version()

# ---------------------------------------------------------------------------
# CSS global
# ---------------------------------------------------------------------------
_GLOBAL_CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;600;700&display=swap');
  html, body, [class*="css"], .stApp {{
      font-family: 'Avenir', 'Nunito', 'Segoe UI', sans-serif !important;
  }}
  .stApp {{ background-color: #f5f9fc !important; }}
  .block-container {{ padding-top: 1.5rem !important; max-width: 1200px; }}

  section[data-testid="stSidebar"] > div:first-child {{
      background-color: {COLOR_SECONDARY} !important;
  }}
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span,
  section[data-testid="stSidebar"] div {{
      color: #ffffff !important;
  }}

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

  .gt-ok {{
      background: {COLOR_SUCCESS}; color: #fff;
      padding: 2px 8px; border-radius: 4px;
      font-size: .75rem; font-weight: 600;
  }}
  .gt-ko {{
      background: {COLOR_DANGER}; color: #fff;
      padding: 2px 8px; border-radius: 4px;
      font-size: .75rem; font-weight: 600;
  }}
  .gt-badge {{
      background: {COLOR_PRIMARY}; color: #fff;
      padding: 2px 7px; border-radius: 4px;
      font-size: .75rem; font-weight: 600;
  }}

  .gt-table {{
      width: 100%; border-collapse: collapse;
      font-size: .85rem; margin-bottom: .75rem;
  }}
  .gt-table th {{
      background: {COLOR_PRIMARY}; color: #fff;
      padding: 7px 10px; text-align: left;
      font-weight: 600; font-size: .82rem;
  }}
  .gt-table td {{
      padding: 6px 10px;
      border-bottom: 1px solid #dde3e8;
      vertical-align: middle;
  }}
  .gt-table tr:hover td {{ background: {COLOR_LIGHT}; }}

  .gt-progress-wrap {{ margin-bottom: 1.2rem; }}
  .gt-progress-header {{
      display: flex; justify-content: space-between;
      margin-bottom: 5px; font-weight: 600;
  }}
  .gt-progress-track {{
      background: #dde3e8; border-radius: 6px;
      height: 13px; overflow: hidden;
  }}
  .gt-progress-fill {{
      height: 100%; border-radius: 6px;
      transition: width .4s ease;
  }}

  .gt-section {{
      border-bottom: 2px solid {COLOR_PRIMARY};
      padding-bottom: 5px;
      margin-top: 1.6rem; margin-bottom: .9rem;
  }}
  .gt-section h5 {{
      color: {COLOR_PRIMARY}; font-weight: 700;
      margin: 0 0 2px 0; font-size: 1rem;
  }}
  .gt-section p {{
      color: #6c757d; font-size: .85rem; margin: 0;
  }}

  .gt-alert {{
      padding: 8px 14px; border-radius: 6px;
      font-size: .9rem; margin-bottom: 10px;
      border-left: 4px solid;
  }}
  .gt-alert-info    {{ background:#dff0fa; color:#0c5174; border-color:{COLOR_PRIMARY}; }}
  .gt-alert-success {{ background:#d4edda; color:#155724; border-color:{COLOR_SUCCESS}; }}
  .gt-alert-warning {{ background:#fff3cd; color:#7a5c00; border-color:{COLOR_WARNING}; }}
  .gt-alert-danger  {{ background:#fde8e8; color:#7b1d1d; border-color:{COLOR_DANGER}; }}

  .gt-card {{
      background: #fff; border-left: 4px solid {COLOR_PRIMARY};
      border-radius: 6px; padding: 12px 16px;
      margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.06);
  }}
  .gt-card-title {{
      font-weight: 600; color: {COLOR_PRIMARY};
      margin-bottom: 4px; font-size: .9rem;
  }}

  /* Logo + méta sidebar */
  .gt-sidebar-footer {{
      position: fixed;
      bottom: 1.2rem;
      left: 0;
      width: var(--sidebar-width, 18rem);
      padding: 0 1.2rem;
      text-align: center;
  }}
  .gt-sidebar-footer a {{
      display: inline-block;
      background: #ffffff;
      padding: 2pt;
      border-radius: 4px;
      opacity: .9;
      transition: opacity .2s;
  }}
  .gt-sidebar-footer a:hover {{ opacity: 1; }}
  .gt-sidebar-footer img {{
      max-width: 100%;
      height: auto;
      display: block;
  }}
  .gt-sidebar-meta {{
      margin-top: 6px;
      font-size: .72rem;
      color: rgba(255,255,255,.6);
      letter-spacing: .02em;
  }}
</style>
"""


def inject_styles() -> None:
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def sidebar_logo() -> None:
    date_str = datetime.now().strftime("%m/%Y")
    logo_html = (
        f'<a href="https://aperto-nota.fr" target="_blank" rel="noopener">'
        f'<img src="data:image/png;base64,{_LOGO_B64}" alt="Aperto Nota">'
        f'</a>'
        if _LOGO_B64 else ""
    )
    st.markdown(
        f'<div class="gt-sidebar-footer">{logo_html}'
        f'<div class="gt-sidebar-meta">{date_str} &nbsp;·&nbsp; v{_VERSION}</div></div>',
        unsafe_allow_html=True,
    )


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
        f'<div class="gt-progress-wrap">'
        f'<div class="gt-progress-header"><span>{label}</span>'
        f'<span style="color:{color};">{pct} %</span></div>'
        f'<div class="gt-progress-track">'
        f'<div class="gt-progress-fill" style="width:{pct}%;background:{color};"></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def alert(message: str, level: str = "info") -> None:
    st.markdown(f'<div class="gt-alert gt-alert-{level}">{message}</div>', unsafe_allow_html=True)


def section_header(title: str, subtitle: str = "") -> None:
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="gt-section"><h5>{title}</h5>{sub}</div>', unsafe_allow_html=True)
