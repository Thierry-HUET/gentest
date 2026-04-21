"""
loader.py – Chargement de fichiers tabulaires (CSV, XLSX, Parquet).
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".parquet"}

_CSV_SEPARATORS = [",", ";", "\t", "|"]


def _detect_csv_separator(source: str | Path | io.BytesIO) -> str:
    try:
        if isinstance(source, io.BytesIO):
            pos = source.tell()
            raw = source.read(4096).decode("utf-8", errors="replace")
            source.seek(pos)
        else:
            with open(source, encoding="utf-8", errors="replace") as f:
                raw = "".join(f.readline() for _ in range(4))
    except Exception:
        return ","

    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return ","

    first = lines[0]
    counts = {sep: first.count(sep) for sep in _CSV_SEPARATORS}
    best = max(counts, key=lambda s: counts[s])
    return best if counts[best] > 0 else ","


def load_file(source: str | Path | io.BytesIO, filename: str = "") -> pd.DataFrame:
    name = filename or (str(source) if not isinstance(source, io.BytesIO) else "")
    ext = Path(name).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Format non supporté : '{ext}'. "
            f"Formats acceptés : {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext == ".csv":
        sep = _detect_csv_separator(source)
        if isinstance(source, io.BytesIO):
            source.seek(0)
        return pd.read_csv(source, sep=sep)

    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(source)

    if ext == ".parquet":
        return pd.read_parquet(source)

    raise ValueError(f"Format non supporté : '{ext}'")
