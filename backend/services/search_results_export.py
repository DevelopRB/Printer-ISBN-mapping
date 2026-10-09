"""Excel export for ISBN Search Results (display-only).

Writes rows supplied by the frontend from already-loaded search results.
Does NOT fetch printers, run reconciliation, or re-extract dates.
"""

from __future__ import annotations

from io import BytesIO

from services.normalized_export import format_ops_date

SEARCH_EXPORT_HEADERS = [
    "ISBN",
    "List A",
    "Printer",
    "Print Date",
    "Job End",
    "Print Start",
    "Job Accept",
    "Result",
    "Set Number",
    "Output Set",
    "Source Filename",
    "Status",
]


def build_search_results_excel(rows: list[dict]) -> bytes:
    """Build an .xlsx workbook from search-result row dicts.

    Expected keys (snake_case): isbn, list_a, printer, print_date, job_end,
    print_start, job_accept, result, set_number, output_set, source_filename, status.

    ``print_date`` must be the same printer Print Date already shown in the UI
    (ISO YYYY-MM-DD or ops display form). Empty for NOT FOUND / CONNECTION ISSUE.
    """
    import xlsxwriter

    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True, "strings_to_numbers": False})
    ws = workbook.add_worksheet("ISBN Search Results")

    header_fmt = workbook.add_format({"bold": True, "bg_color": "#E2E8F0", "border": 1})
    text_fmt = workbook.add_format({"border": 1})

    for col, title in enumerate(SEARCH_EXPORT_HEADERS):
        ws.write(0, col, title, header_fmt)

    for r_idx, row in enumerate(rows, start=1):
        raw_date = row.get("print_date")
        # Preserve blank for undated rows; format ISO → ops display when present
        print_date_display = format_ops_date(str(raw_date).strip()) if raw_date else ""

        values = [
            str(row.get("isbn") or ""),
            str(row.get("list_a") or "N/A"),
            str(row.get("printer") or ""),
            print_date_display,
            str(row.get("job_end") or ""),
            str(row.get("print_start") or ""),
            str(row.get("job_accept") or ""),
            str(row.get("result") or ""),
            str(row.get("set_number") if row.get("set_number") is not None else ""),
            str(row.get("output_set") if row.get("output_set") is not None else ""),
            str(row.get("source_filename") or ""),
            str(row.get("status") or ""),
        ]
        for c_idx, value in enumerate(values):
            ws.write(r_idx, c_idx, value, text_fmt)

    ws.set_column(0, 0, 16)
    ws.set_column(1, 2, 12)
    ws.set_column(3, 3, 14)  # Print Date
    ws.set_column(4, 6, 12)
    ws.set_column(7, 9, 12)
    ws.set_column(10, 10, 40)
    ws.set_column(11, 11, 16)

    workbook.close()
    return buffer.getvalue()
