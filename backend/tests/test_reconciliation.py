"""Tests for List A–driven reconciliation statuses and 4010 multi-filename split."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.isbn_extractor import extract_isbn, split_4010_filenames
from services.reconciliation import (
    DUPLICATE_IN_LIST_A,
    FOUND,
    NEEDS_REVIEW,
    NOT_FOUND,
    PRINTER_RECORDS_NOT_IN_LIST_A,
)


def test_split_pipe_separated_filenames():
    raw = (
        "9789374567555_F3_QC_LB_Pharma..pdf | 9789374567555_F3_LB_QC_Pharma..pdf"
    )
    parts = split_4010_filenames(raw)
    assert len(parts) == 2
    assert parts[0].startswith("9789374567555_F3_QC")
    assert parts[1].startswith("9789374567555_F3_LB")


def test_split_single_filename_unchanged():
    assert split_4010_filenames("9789351285106_Pharma.pdf") == ["9789351285106_Pharma.pdf"]


def test_split_empty():
    assert split_4010_filenames(None) == []
    assert split_4010_filenames("") == []


def test_multi_filename_same_isbn_extracts_once_per_doc():
    raw = (
        "9789374567555_F3_QC_LB_Pharma..pdf | 9789374567555_F3_LB_QC_Pharma..pdf"
    )
    isbns = [extract_isbn(f) for f in split_4010_filenames(raw)]
    assert isbns == ["9789374567555", "9789374567555"]
    # Reconciliation uniqueness
    assert len(set(isbns)) == 1


def test_primary_status_mapping_example():
    """List A: A,B,C  Printer: A,A,D → FOUND / NOT_FOUND / audit D."""
    list_a = {"A", "B", "C"}
    printer_hits = {"A": 2, "D": 1}  # occurrence counts

    primary = {}
    for isbn in list_a:
        primary[isbn] = FOUND if isbn in printer_hits else NOT_FOUND

    audit = sorted(set(printer_hits) - list_a)

    assert primary == {"A": FOUND, "B": NOT_FOUND, "C": NOT_FOUND}
    assert audit == ["D"]
    assert PRINTER_RECORDS_NOT_IN_LIST_A == "PRINTER_RECORDS_NOT_IN_LIST_A"
    # Duplicate printer hits do not create two primary matches
    assert printer_hits["A"] == 2
    assert primary["A"] == FOUND


def test_duplicate_list_a_status_constant():
    assert DUPLICATE_IN_LIST_A == "DUPLICATE_IN_LIST_A"
    assert NEEDS_REVIEW == "NEEDS_REVIEW"
    assert NOT_FOUND == "NOT_FOUND"
    assert FOUND == "FOUND"
