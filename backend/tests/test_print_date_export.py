"""Additional tests for Print Date mapping in normalized export."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl

from services.normalized_export import (
    PRESENT,
    NOT_FOUND,
    SKIP_REASON_NO_ISBN,
    build_normalized_workbook,
    classify_4010_values,
    format_ops_date,
    unique_print_dates_display,
)


def _sheets(buffer):
    buffer.seek(0)
    return openpyxl.load_workbook(buffer, data_only=True)


def _sheet2_header_row(ws):
    for r in range(1, 12):
        if ws.cell(r, 1).value == "ISBN" and ws.cell(r, 2).value == "Print Date":
            return r
    raise AssertionError("Sheet 2 header not found")


def _sheet3_header_row(ws):
    for r in range(1, 12):
        if ws.cell(r, 1).value == "List A ISBN" and ws.cell(r, 3).value == "Print Date":
            return r
    raise AssertionError("Sheet 3 header not found")


def test_format_ops_date():
    assert format_ops_date("2026-08-27") == "27-Aug-2026"
    assert format_ops_date("2026-08-01") == "01-Aug-2026"


def test_unique_print_dates_display():
    assert unique_print_dates_display(["2026-08-26", "2026-08-27", "2026-08-27"]) == (
        "26-Aug-2026, 27-Aug-2026"
    )


def test_unique_printers_display():
    from services.normalized_export import unique_printers_display

    assert unique_printers_display(["Printer 1", "Printer 2", "Printer 1"]) == (
        "Printer 1, Printer 2"
    )


def test_classify_keeps_date_with_same_row():
    classified = classify_4010_values(
        [
            "9789393103792_F4_QC SD_Pharma.pdf",
            "CE Adjust",
            "8888001171897_F2.pdf",
            "8888001171897_F3.pdf",
        ],
        print_dates=["2026-08-27", "2026-08-26", "2026-08-26", "2026-08-27"],
        job_ids=["87816", "1", "2", "3"],
    )
    assert [(t.normalized_identifier, t.print_date) for t in classified.extracted] == [
        ("9789393103792", "2026-08-27"),
        ("8888001171897", "2026-08-26"),
        ("8888001171897", "2026-08-27"),
    ]
    assert len(classified.skipped) == 1
    assert classified.skipped[0].printer_record == "CE Adjust"


def test_sheet2_has_print_date_column():
    rows = [
        ("9789393103792", "2026-08-27", "9789393103792_F4_QC SD_Pharma.pdf"),
        ("9789368338758", "2026-08-27", "9789368338758_F2_QC SD_Pharma.pdf"),
        ("9789353039851", "2026-08-26", "Pub_9789353039851-F4.pdf"),
    ]
    buf = build_normalized_workbook(["9789393103792"], rows)
    ws = _sheets(buf)["Printer ISBNs"]
    hdr = _sheet2_header_row(ws)
    assert [ws.cell(hdr, c).value for c in range(1, 4)] == [
        "ISBN",
        "Print Date",
        "Source Filename",
    ]
    assert [ws.cell(hdr + 1, c).value for c in range(1, 4)] == [
        "9789393103792",
        "27-Aug-2026",
        "9789393103792_F4_QC SD_Pharma.pdf",
    ]
    assert ws.cell(hdr + 3, 2).value == "26-Aug-2026"


def test_sheet3_aggregates_unique_dates():
    list_a = ["8888001171897", "8888001171897", "9789375480896"]
    printer = [
        ("8888001171897", "2026-08-26", "8888001171897_F2.pdf"),
        ("8888001171897", "2026-08-27", "8888001171897_F3.pdf"),
        ("8888001171897", "2026-08-27", "8888001171897_F3b.pdf"),
    ]
    buf = build_normalized_workbook(list_a, printer)
    ws = _sheets(buf)["Reconciliation"]
    hdr = _sheet3_header_row(ws)
    assert [ws.cell(hdr, c).value for c in range(1, 6)] == [
        "List A ISBN",
        "Printer ISBN",
        "Print Date",
        "Printer",
        "Status",
    ]
    assert ws.max_row == hdr + 3  # header + 3 List A rows (duplicate preserved)
    assert [ws.cell(hdr + 1, c).value for c in range(1, 6)] == [
        "8888001171897",
        "8888001171897",
        "26-Aug-2026, 27-Aug-2026",
        "",
        PRESENT,
    ]
    assert [ws.cell(hdr + 2, c).value for c in range(1, 6)] == [
        "8888001171897",
        "8888001171897",
        "26-Aug-2026, 27-Aug-2026",
        "",
        PRESENT,
    ]
    assert [
        ws.cell(hdr + 3, 1).value,
        ws.cell(hdr + 3, 2).value or "",
        ws.cell(hdr + 3, 3).value or "",
        ws.cell(hdr + 3, 4).value or "",
        ws.cell(hdr + 3, 5).value,
    ] == ["9789375480896", "", "", "", NOT_FOUND]


def test_sheet3_shows_printer_with_dates():
    list_a = ["8888001171897", "9789375480896"]
    buf = build_normalized_workbook(
        list_a,
        printer_sheets=[
            (
                "Printer 1 ISBNs",
                [("8888001171897", "2026-08-26", "a.pdf", "Printer 1")],
            ),
            (
                "Printer 2 ISBNs",
                [
                    ("8888001171897", "2026-08-27", "b.pdf", "Printer 2"),
                    ("8888001171897", "2026-08-27", "c.pdf", "Printer 2"),
                ],
            ),
        ],
    )
    ws = _sheets(buf)["Reconciliation"]
    hdr = _sheet3_header_row(ws)
    assert [ws.cell(hdr + 1, c).value for c in range(1, 6)] == [
        "8888001171897",
        "8888001171897",
        "26-Aug-2026, 27-Aug-2026",
        "Printer 1, Printer 2",
        PRESENT,
    ]
    assert (ws.cell(hdr + 2, 4).value or "") == ""
    assert ws.cell(hdr + 2, 5).value == NOT_FOUND


def test_sheet_starts_with_data_headers_only():
    buf = build_normalized_workbook(
        ["8888001171897"],
        [("8888001171897", "2026-08-25", "8888001171897_F2.pdf")],
    )
    ws1 = _sheets(buf)["List A ISBNs"]
    assert ws1.cell(1, 1).value == "ISBN"
    assert ws1.cell(1, 1).value != "Printer"
    ws2 = _sheets(buf)["Printer ISBNs"]
    assert [ws2.cell(1, c).value for c in range(1, 4)] == [
        "ISBN",
        "Print Date",
        "Source Filename",
    ]
    assert ws2.cell(2, 2).value == "25-Aug-2026"
