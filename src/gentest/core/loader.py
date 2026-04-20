"""
loader.py – Chargement de fichiers tabulaires (CSV, XLSX, Parquet).
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".parquet"}


def load_file(source: str | Path | io.BytesIO, filename: str = "") -> pd.DataFrame:
    """
    Charge un fichier tabulaire et retourne un DataFrame.

    Parameters
    ----------
    source   : chemin, objet Path ou buffer BytesIO
    filename : nom du fichier (utile si source est un buffer)

    Returns
    -------
    pd.DataFrame

    Raises
    ------
    ValueError si le format n'est pas supporté.
    """
    name = filename or (str(source) if not isinstance(source, io.BytesIO) else "")
    ext = Path(name).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Format non supporté : '{ext}'. "
            f"Formats acceptés : {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext == ".csv":
        return pd.read_csv(source)
    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(source)
    if ext == ".parquet":
        return pd.read_parquet(source)

    raise ValueError(f"Format non supporté : '{ext}'")  # garde-fou
