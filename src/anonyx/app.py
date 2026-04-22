"""
app.py – Point d'entrée Streamlit — anonyx_Gen.

Lancement :
    streamlit run src/anonyx/app.py
"""
import sys
import traceback

from anonyx.core.logger import get_logger
from anonyx.ui.layout import run_app

log = get_logger(__name__)


def _excepthook(exc_type, exc_value, exc_tb):
    """Capture toute exception non gérée avant que Python ne s'arrête."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    log.critical(
        "Exception non gérée : %s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )


sys.excepthook = _excepthook


def main() -> None:
    try:
        run_app()
    except Exception:
        log.error("Erreur non gérée dans run_app", exc_info=True)
        raise  # Laisser Streamlit afficher son message d'erreur


main()
