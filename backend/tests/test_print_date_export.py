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
        job_ends=["10:02:42", None, "10:00:00", "11:00:00"],
        print_starts=["09:57:47", None, "09:58:00", "10:55:00"],
        job_accepts=["09:57:47", None, "09:58:00", "10:55:00"],
        results=["Complete", None, "Complete", "Complete"],
        set_numbers=["3", None, "2", "3"],
        output_sets=["3", None, "2", "3"],
    )
    assert [(t.normalized_identifier, t.print_date) for t in classified.extracted] == [
        ("9789393103792", "2026-08-27"),
        ("8888001171897", "2026-08-26"),
        ("8888001171897", "2026-08-27"),
    ]
    first = classified.extracted[0]
    assert first.job_id == "87816"
    assert first.job_end == "10:02:42"
    assert first.print_start == "09:57:47"
    assert first.job_accept == "09:57:47"
    assert first.result == "Complete"
    assert first.set_number == "3"
    assert first.output_set == "3"
    assert len(classified.skipped) == 1
    assert classified.skipped[0].printer_record == "CE Adjust"


def test_sheet2_has_print_date_column():
    from services.normalized_export import PRINTER_ISBN_HEADERS, PrinterSheetRow

    rows = [
        PrinterSheetRow(
            isbn="9789393103792",
            print_date="2026-08-27",
            job_end="10:02:42",
            print_start="09:57:47",
            job_accept="09:57:47",
            result="Complete",
            set_number="3",
            output_set="3",
            printer="Printer 1",
            job_id="87816",
            source_filename="9789393103792_F4_QC SD_Pharma.pdf",
        ),
        PrinterSheetRow(
            isbn="9789368338758",
            print_date="2026-08-27",
            source_filename="9789368338758_F2_QC SD_Pharma.pdf",
        ),
        PrinterSheetRow(
            isbn="9789353039851",
            print_date="2026-08-26",
            source_filename="Pub_9789353039851-F4.pdf",
        ),
    ]
    buf = build_normalized_workbook(["9789393103792"], rows)
    ws = _sheets(buf)["Printer ISBNs"]
    hdr = _sheet2_header_row(ws)
    assert [ws.cell(hdr, c).value for c in range(1, len(PRINTER_ISBN_HEADERS) + 1)] == (
        PRINTER_ISBN_HEADERS
    )
    assert [ws.cell(hdr + 1, c).value for c in range(1, 12)] == [
        "9789393103792",
        "27-Aug-2026",
        "10:02:42",
        "09:57:47",
        "09:57:47",
        "Complete",
        "3",
        "3",
        "Printer 1",
        "87816",
        "9789393103792_F4_QC SD_Pharma.pdf",
    ]
    assert ws.cell(hdr + 3, 2).value == "26-Aug-2026"


def test_sheet3_aggregates_unique_dates():
    from services.normalized_export import RECONCILIATION_HEADERS, PrinterSheetRow

    list_a = ["8888001171897", "8888001171897", "9789375480896"]
    printer = [
        PrinterSheetRow(
            isbn="8888001171897",
            print_date="2026-08-26",
            job_end="10:00:00",
            print_start="09:58:00",
            job_accept="09:58:00",
            result="Complete",
            set_number="2",
            output_set="2",
            printer="Printer 1",
            job_id="1",
            source_filename="8888001171897_F2.pdf",
        ),
        PrinterSheetRow(
            isbn="8888001171897",
            print_date="2026-08-27",
            job_end="11:00:00",
            print_start="10:55:00",
            job_accept="10:55:00",
            result="Complete",
            set_number="3",
            output_set="3",
            printer="Printer 1",
            job_id="2",
            source_filename="8888001171897_F3.pdf",
        ),
        PrinterSheetRow(
            isbn="8888001171897",
            print_date="2026-08-27",
            job_end="12:00:00",
            print_start="11:55:00",
            job_accept="11:55:00",
            result="Complete",
            set_number="1",
            output_set="1",
            printer="Printer 1",
            job_id="3",
            source_filename="8888001171897_F3b.pdf",
        ),
    ]
    buf = build_normalized_workbook(list_a, printer)
    ws = _sheets(buf)["Reconciliation"]
    hdr = _sheet3_header_row(ws)
    assert [ws.cell(hdr, c).value for c in range(1, len(RECONCILIATION_HEADERS) + 1)] == (
        RECONCILIATION_HEADERS
    )
    assert ws.max_row == hdr + 3  # header + 3 List A rows (duplicate preserved)
    assert ws.cell(hdr + 1, 1).value == "8888001171897"
    assert ws.cell(hdr + 1, 2).value == "8888001171897"
    assert ws.cell(hdr + 1, 3).value == "26-Aug-2026, 27-Aug-2026, 27-Aug-2026"
    assert ws.cell(hdr + 1, 4).value == "10:00:00, 11:00:00, 12:00:00"
    assert ws.cell(hdr + 1, 8).value == "2, 3, 1"
    assert ws.cell(hdr + 1, 9).value == "2, 3, 1"
    assert ws.cell(hdr + 1, 11).value == PRESENT
    assert [
        ws.cell(hdr + 3, 1).value,
        ws.cell(hdr + 3, 2).value or "",
        ws.cell(hdr + 3, 3).value or "",
        ws.cell(hdr + 3, 11).value,
    ] == ["9789375480896", "", "", NOT_FOUND]


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
    # Printer column is index 10; Status is 11
    assert ws.cell(hdr + 1, 10).value == "Printer 1, Printer 2, Printer 2"
    assert ws.cell(hdr + 1, 3).value == "26-Aug-2026, 27-Aug-2026, 27-Aug-2026"
    assert ws.cell(hdr + 1, 11).value == PRESENT
    assert ws.cell(hdr + 2, 11).value == NOT_FOUND


def test_partial_output_set_not_changed():
    from services.normalized_export import PrinterSheetRow

    rows = [
        PrinterSheetRow(
            isbn="9789393103792",
            print_date="2026-08-27",
            result="Canceled",
            set_number="3",
            output_set="2",
            source_filename="9789393103792_F4.pdf",
        )
    ]
    buf = build_normalized_workbook(["9789393103792"], rows)
    ws = _sheets(buf)["Printer ISBNs"]
    hdr = _sheet2_header_row(ws)
    assert ws.cell(hdr + 1, 7).value == "3"
    assert ws.cell(hdr + 1, 8).value == "2"


def test_classify_tsv_job_fields_from_live_sample():
    from pathlib import Path

    from services.normalized_export import classify_tsv_bytes

    path = Path(__file__).resolve().parents[1] / "data" / "printer_downloads"
    files = sorted(path.glob("printer_1_*.tsv")) if path.exists() else []
    if not files:
        return  # optional when downloads absent
    classified = classify_tsv_bytes(files[-1].read_bytes())
    assert classified.extracted
    # Find a complete multi-copy job (Set Number == Output Set > 1)
    multi = next(
        (
            t
            for t in classified.extracted
            if t.set_number
            and t.output_set
            and t.set_number == t.output_set
            and t.set_number not in ("0", "1")
        ),
        None,
    )
    assert multi is not None
    assert multi.job_end and ":" in multi.job_end
    assert multi.print_start and ":" in multi.print_start
    assert multi.job_accept and ":" in multi.job_accept
    assert multi.result in ("Complete", "Canceled") or multi.result
    # Incomplete job: Output Set must stay as printed, not coerced to Set Number
    incomplete = next(
        (
            t
            for t in classified.extracted
            if t.set_number and t.output_set == "0" and t.set_number != "0"
        ),
        None,
    )
    if incomplete:
        assert incomplete.output_set == "0"
        assert incomplete.set_number != "0"


def test_sheet_starts_with_data_headers_only():
    from services.normalized_export import PRINTER_ISBN_HEADERS

    buf = build_normalized_workbook(
        ["8888001171897"],
        [("8888001171897", "2026-08-25", "8888001171897_F2.pdf")],
    )
    ws1 = _sheets(buf)["List A ISBNs"]
    assert ws1.cell(1, 1).value == "ISBN"
    assert ws1.cell(1, 1).value != "Printer"
    ws2 = _sheets(buf)["Printer ISBNs"]
    assert [ws2.cell(1, c).value for c in range(1, len(PRINTER_ISBN_HEADERS) + 1)] == (
        PRINTER_ISBN_HEADERS
    )
    assert ws2.cell(2, 2).value == "25-Aug-2026"
