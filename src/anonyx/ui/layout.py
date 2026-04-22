"""
layout.py – Orchestrateur Streamlit — Midara (Projet Anonyx).

Gère :
  - Configuration de la page
  - Sidebar (paramètres + navigation)
  - Routage vers page_home ou page_stats
"""
from __future__ import annotations

import streamlit as st

from anonyx.ui.components import inject_styles, sidebar_logo
from anonyx.ui import page_home, page_stats
from anonyx.core.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
_PAGES = {
    "🏠  Accueil":      "home",
    "📊  Statistiques": "stats",
}


def _sidebar() -> tuple[str, int, int, float, float, float]:
    """
    Affiche la sidebar et retourne les paramètres de génération.
    Le file uploader a été déplacé vers la page d'accueil.
    """
    with st.sidebar:
        st.markdown("<div style='padding:.6rem 0 .4rem 0;'></div>", unsafe_allow_html=True)

        # ── Navigation ────────────────────────────────────────────────────────
        st.markdown(
            "<p style='font-size:.85rem;font-weight:600;margin-bottom:6px;'>Navigation</p>",
            unsafe_allow_html=True,
        )
        page_label = st.radio(
            "Navigation",
            list(_PAGES.keys()),
            label_visibility="collapsed",
        )
        st.markdown("---")

        # ── Paramètres de génération ──────────────────────────────────────────
        st.markdown(
            "<p style='font-size:.85rem;font-weight:600;margin-bottom:4px;'>"
            "Nombre de lignes à générer</p>",
            unsafe_allow_html=True,
        )
        n_rows = st.number_input(
            "Lignes", min_value=10, max_value=1_000_000,
            value=1000, step=100, label_visibility="collapsed",
        )
        st.markdown("---")

        with st.expander("⚙ Paramètres avancés", expanded=False):
            st.markdown(
                "<p style='font-size:.8rem;font-weight:600;margin-bottom:4px;'>"
                "Reproductibilité</p>",
                unsafe_allow_html=True,
            )
            seed = st.number_input("Seed", min_value=0, value=42)
            st.markdown(
                "<p style='font-size:.8rem;font-weight:600;margin:8px 0 4px;'>"
                "Tolérances de conformité</p>",
                unsafe_allow_html=True,
            )
            tolerance      = st.slider("Tolérance numérique (%)", 1, 20, 5) / 100
            js_threshold   = st.slider("Seuil Jensen-Shannon", 0.01, 0.20, 0.05, step=0.01)
            regex_min_rate = st.slider("Conformité regex min. (%)", 50, 100, 95) / 100

        sidebar_logo()

    return _PAGES[page_label], int(n_rows), int(seed), tolerance, js_threshold, regex_min_rate


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------
def run_app() -> None:
    st.set_page_config(
        page_title="Midara – Générateur de jeu de test",
        page_icon="🧪",
        layout="wide",
    )
    inject_styles()

    page, n_rows, seed, tolerance, js_threshold, regex_min_rate = _sidebar()

    # Stocker les paramètres de tolérance dans la session (utilisés par page_stats)
    st.session_state["tolerance"]      = tolerance
    st.session_state["js_threshold"]   = js_threshold
    st.session_state["regex_min_rate"] = regex_min_rate

    if page == "home":
        page_home.render(
            n_rows=n_rows,
            seed=seed,
            tolerance=tolerance,
            js_threshold=js_threshold,
            regex_min_rate=regex_min_rate,
        )
    elif page == "stats":
        page_stats.render()
