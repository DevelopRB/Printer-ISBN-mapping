"""Excel / CSV parsing utilities with flexible column detection."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from logging_config import logger


def normalize_header(name: Any) -> str:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    text = str(name).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


ISBN_ALIASES = {
    "isbn",
    "isbnno",
    "isbnnumber",
    "isbn13",
    "isbn10",
    "isbncode",
    "bookisbn",
}

DATE_ALIASES = {"date", "dates", "listdate", "printdate", "entrydate"}
VCH_ALIASES = {"vchno", "voucherno", "voucher", "vchnumber", "vouchernumber", "vno"}
PARTY_ALIASES = {"party", "partyname", "customer", "client"}
ITEM_ALIASES = {"item", "itemname", "book", "bookname", "title", "product", "description"}
UNIT_ALIASES = {"unit", "uom"}
PENDING_QTY_ALIASES = {
    "pendingqty",
    "pending",
    "qty",
    "quantity",
    "pendingquantity",
    "balqty",
    "balanceqty",
}

PRINTER_SOURCE_ALIASES = {
    "4010",
    "filename",
    "file",
    "file name",
    "pdf",
    "pdfname",
    "source",
    "document",
}


class ColumnDetectionError(Exception):
    pass


def read_tabular_file(file_path: str | Path) -> pd.DataFrame:
    """Read .xlsx, .xls, or .csv into a DataFrame. All cells as strings where possible."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    try:
        if suffix == ".csv":
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        elif suffix == ".xls":
            df = pd.read_excel(path, dtype=str, engine="xlrd")
        elif suffix in (".xlsx", ".xlsm"):
            df = pd.read_excel(path, dtype=str, engine="openpyxl")
        else:
            # Attempt auto-detect
            try:
                df = pd.read_excel(path, dtype=str, engine="openpyxl")
            except Exception:
                df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception as exc:
        logger.error("Failed to parse file %s: %s", path.name, exc)
        raise ValueError(f"Could not read file '{path.name}'. Ensure it is a valid Excel or CSV file.") from exc

    # Normalize empty / nan
    df = df.fillna("")
    df.columns = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(df.columns)]
    return df


def detect_column(columns: list[str], aliases: set[str], required_label: str) -> str | None:
    normalized_map = {normalize_header(c): c for c in columns}
    for alias in aliases:
        if alias in normalized_map:
            return normalized_map[alias]
    # Partial contains match for longer headers
    for norm, original in normalized_map.items():
        for alias in aliases:
            if alias and (alias in norm or norm in alias):
                return original
    return None


def detect_list_a_columns(columns: list[str]) -> dict[str, str | None]:
    mapping = {
        "isbn": detect_column(columns, ISBN_ALIASES, "ISBN"),
        "date": detect_column(columns, DATE_ALIASES, "Date"),
        "voucher_no": detect_column(columns, VCH_ALIASES, "Vch No."),
        "party": detect_column(columns, PARTY_ALIASES, "Party"),
        "item": detect_column(columns, ITEM_ALIASES, "Item"),
        "unit": detect_column(columns, UNIT_ALIASES, "Unit"),
        "pending_qty": detect_column(columns, PENDING_QTY_ALIASES, "Pending Qty"),
    }
    return mapping


def detect_printer_source_column(columns: list[str]) -> str | None:
    # Exact / normalized match for 4010 first
    for col in columns:
        if normalize_header(col) == "4010" or str(col).strip() == "4010":
            return col

    found = detect_column(columns, {normalize_header(a) for a in PRINTER_SOURCE_ALIASES}, "4010")
    if found:
        return found

    # Heuristic: column whose sample values look like filenames with ISBNs
    return None


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert DataFrame to list of dicts preserving original column names."""
    records = []
    for idx, row in df.iterrows():
        raw = {str(k): ("" if v is None else str(v)) for k, v in row.items()}
        records.append({"source_row_number": int(idx) + 2, "raw": raw})  # +2: header is row 1
    return records
