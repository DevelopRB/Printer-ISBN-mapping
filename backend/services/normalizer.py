"""Normalize List A and printer upload rows into structured records."""

from __future__ import annotations

import json
from typing import Any

from services.excel_parser import (
    ColumnDetectionError,
    dataframe_to_records,
    detect_list_a_columns,
    detect_printer_source_column,
    read_tabular_file,
)
from services.isbn_extractor import extract_isbn, split_4010_filenames
from services.isbn_validator import validate_and_normalize
from logging_config import logger


def _safe_get(raw: dict, key: str | None) -> str | None:
    if not key:
        return None
    val = raw.get(key, "")
    if val is None:
        return None
    text = str(val).strip()
    return text if text else None


def normalize_list_a(file_path: str) -> dict[str, Any]:
    """Parse and normalize List A. Raises ValueError on missing ISBN column."""
    df = read_tabular_file(file_path)
    columns = list(df.columns)
    mapping = detect_list_a_columns(columns)

    if not mapping["isbn"]:
        logger.error("ISBN column not found in List A. Columns: %s", columns)
        raise ColumnDetectionError("Could not find an ISBN column in List A.")

    rows = dataframe_to_records(df)
    records = []
    valid_isbn_count = 0

    for row in rows:
        raw = row["raw"]
        isbn_original = _safe_get(raw, mapping["isbn"])
        isbn_normalized = None
        is_valid = 0

        if isbn_original:
            # Try direct validation first, then extraction
            isbn_normalized = validate_and_normalize(isbn_original)
            if not isbn_normalized:
                isbn_normalized = extract_isbn(isbn_original)

        if isbn_normalized:
            is_valid = 1
            valid_isbn_count += 1

        records.append(
            {
                "source_row_number": row["source_row_number"],
                "isbn_original": isbn_original,
                "isbn_normalized": isbn_normalized,
                "is_valid_isbn": is_valid,
                "date": _safe_get(raw, mapping["date"]),
                "voucher_no": _safe_get(raw, mapping["voucher_no"]),
                "party": _safe_get(raw, mapping["party"]),
                "item": _safe_get(raw, mapping["item"]),
                "unit": _safe_get(raw, mapping["unit"]),
                "pending_qty": _safe_get(raw, mapping["pending_qty"]),
                "raw_data_json": json.dumps(raw, ensure_ascii=False),
            }
        )

    return {
        "isbn_column": mapping["isbn"],
        "column_mapping": mapping,
        "record_count": len(records),
        "isbn_detected_count": valid_isbn_count,
        "records": records,
    }


def normalize_printer(file_path: str) -> dict[str, Any]:
    """Parse and normalize a printer file. Raises on missing 4010/source column."""
    df = read_tabular_file(file_path)
    columns = list(df.columns)
    source_col = detect_printer_source_column(columns)

    if not source_col:
        logger.error("Printer field 4010 not found. Columns: %s", columns)
        raise ColumnDetectionError("Could not find printer field 4010.")

    # Optional date column
    date_col = None
    for col in columns:
        n = "".join(ch for ch in str(col).lower() if ch.isalnum())
        if n in ("date", "printdate", "dates"):
            date_col = col
            break

    rows = dataframe_to_records(df)
    records = []
    isbn_count = 0
    not_found = 0

    for row in rows:
        raw = row["raw"]
        raw_4010 = _safe_get(raw, source_col)
        printer_date = _safe_get(raw, date_col) if date_col else None
        # Expand multi-filename 4010 values into separate document rows
        filenames = split_4010_filenames(raw_4010) if raw_4010 else [None]
        if not filenames:
            filenames = [None]

        for filename in filenames:
            isbn_normalized = extract_isbn(filename) if filename else None
            is_valid = 1 if isbn_normalized else 0
            status = None if isbn_normalized else "ISBN_NOT_FOUND"

            if isbn_normalized:
                isbn_count += 1
            else:
                not_found += 1

            enriched = dict(raw)
            enriched["_raw_4010_value"] = raw_4010
            enriched["_original_filename"] = filename

            records.append(
                {
                    "source_row_number": row["source_row_number"],
                    "source_value": filename,  # per-document; raw 4010 kept in JSON
                    "isbn_normalized": isbn_normalized,
                    "is_valid_isbn": is_valid,
                    "status": status,
                    "printer_date": printer_date,
                    "raw_data_json": json.dumps(enriched, ensure_ascii=False),
                }
            )

    return {
        "source_column": source_col,
        "record_count": len(records),
        "isbn_detected_count": isbn_count,
        "isbn_not_found_count": not_found,
        "records": records,
    }
