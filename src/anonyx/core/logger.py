"""
logger.py – Configuration centralisée du logger Midara.

Rotation par taille : 5 Mo max · 3 fichiers conservés
Format  : ISO-8601 | LEVEL    | module:ligne | message
Niveaux : WARNING et supérieur en production (WARNING, ERROR, CRITICAL)
          + INFO pour les événements métier

Usage
-----
    from anonyx.core.logger import get_logger
    log = get_logger(__name__)

    log.info("Fichier chargé : %s (%d lignes)", filename, n)
    log.warning("Colonne '%s' ignorée : trop de nulls", col)
    log.error("Erreur de génération", exc_info=True)
"""
from __future__ import annotations

import logging
import logging.handlers
import warnings
from pathlib import Path


# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[3]   # gentest/
_LOG_DIR      = _PROJECT_ROOT / "log"
_LOG_FILE     = _LOG_DIR / "midara.log"

# ---------------------------------------------------------------------------
# Paramètres de rotation
# ---------------------------------------------------------------------------
_MAX_BYTES    = 5 * 1024 * 1024   # 5 Mo
_BACKUP_COUNT = 3                  # midara.log · midara.log.1 · midara.log.2

# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------
_FMT     = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# Initialisation (une seule fois par processus)
# ---------------------------------------------------------------------------
_initialized = False


def _setup() -> None:
    global _initialized
    if _initialized:
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("anonyx")
    root.setLevel(logging.INFO)

    # Évite les doublons si Streamlit recharge le module
    if root.handlers:
        _initialized = True
        return

    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    # Handler fichier avec rotation
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Handler console (WARNING+ seulement pour ne pas polluer Streamlit)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # Éviter la propagation vers le root logger de Python
    root.propagate = False

    # ----------------------------------------------------------------
    # Capture des warnings Python (dont ceux de Streamlit/scipy)
    # redirige warnings.warn() vers le système logging
    # ----------------------------------------------------------------
    logging.captureWarnings(True)
    py_warnings_logger = logging.getLogger("py.warnings")
    py_warnings_logger.setLevel(logging.WARNING)
    if not py_warnings_logger.handlers:
        py_warnings_logger.addHandler(fh)  # même fichier rotatif
        py_warnings_logger.propagate = False

    # Filtre : on veut voir les DeprecationWarning (Streamlit les émet)
    warnings.simplefilter("always", DeprecationWarning)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    Retourne un logger hiérarchique sous 'anonyx'.
    Si name commence déjà par 'anonyx', on l'utilise tel quel,
    sinon on le préfixe pour rester dans la hiérarchie.
    """
    _setup()
    qualified = name if name.startswith("anonyx") else f"anonyx.{name}"
    return logging.getLogger(qualified)
