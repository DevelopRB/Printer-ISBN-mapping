"""Excel export of reconciliation results (multi-sheet workbook)."""

from __future__ import annotations

import json
from io import BytesIO

import pandas as pd
from sqlalchemy.orm import Session

from models.models import ListARecord, PrinterRecord, ReconciliationResult
from services.reconciliation import (
    DUPLICATE_IN_LIST_A,
    FOUND,
    NEEDS_REVIEW,
    NOT_FOUND,
    PRINTER_RECORDS_NOT_IN_LIST_A,
    compute_summary,
)


def _parse_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _result_row(r: ReconciliationResult) -> dict:
    printers = _parse_json_list(r.printer_names)
    dates = _parse_json_list(r.printer_dates)
    values = _parse_json_list(r.original_printer_values)
    record_ids = _parse_json_list(r.printer_record_ids)
    return {
        "Status": r.status,
        "ISBN": r.isbn or "",
        "Item": r.item or "",
        "Party": r.party or "",
        "Voucher No.": r.voucher_no or "",
        "List A Date": r.list_a_date or "",
        "Pending Qty": r.pending_qty or "",
        "Printer": ", ".join(printers) if printers else "—",
        "Printer Date": ", ".join(d for d in dates if d) if dates else "—",
        "Printer Occurrences": len(record_ids),
        "Original Filename(s)": " | ".join(v for v in values if v),
    }


def export_workbook(db: Session, project_id: int) -> BytesIO:
    results = (
        db.query(ReconciliationResult)
        .filter(ReconciliationResult.project_id == project_id)
        .order_by(ReconciliationResult.id)
        .all()
    )

    list_a_rows = [
        _result_row(r)
        for r in results
        if r.status in (FOUND, NOT_FOUND, DUPLICATE_IN_LIST_A, NEEDS_REVIEW)
    ]
    found = [_result_row(r) for r in results if r.status == FOUND]
    not_found = [_result_row(r) for r in results if r.status == NOT_FOUND]
    printer_audit = [
        _result_row(r) for r in results if r.status == PRINTER_RECORDS_NOT_IN_LIST_A
    ]
    needs_review = [_result_row(r) for r in results if r.status == NEEDS_REVIEW]

    printer_recs = (
        db.query(PrinterRecord)
        .join(PrinterRecord.upload)
        .filter(PrinterRecord.upload.has(project_id=project_id))
        .all()
    )
    printer_raw_rows = []
    for pr in printer_recs:
        raw_4010 = pr.source_value or ""
        try:
            raw = json.loads(pr.raw_data_json or "{}")
            raw_4010 = raw.get("_raw_4010_value") or raw_4010
        except json.JSONDecodeError:
            pass
        printer_raw_rows.append(
            {
                "Printer ID": pr.printer_id,
                "Printer Date": pr.printer_date or "",
                "Source Row": pr.source_row_number,
                "Raw 4010 Value": raw_4010,
                "Original Filename": pr.source_value or "",
                "ISBN": pr.isbn_normalized or "",
                "Valid": "Yes" if pr.is_valid_isbn else "No",
                "Status": pr.status or "",
            }
        )

    list_a = (
        db.query(ListARecord)
        .join(ListARecord.upload)
        .filter(ListARecord.upload.has(project_id=project_id))
        .all()
    )
    summary = compute_summary(db, project_id)
    summary_rows = [
        {"Section": "List A", "Metric": "List A Records", "Value": summary["list_a_records"]},
        {"Section": "List A", "Metric": "Unique ISBNs", "Value": summary["unique_isbns"]},
        {"Section": "List A", "Metric": "Found", "Value": summary["found"]},
        {"Section": "List A", "Metric": "Not Found", "Value": summary["not_found"]},
        {"Section": "List A", "Metric": "Duplicate List A", "Value": summary["duplicates"]},
        {"Section": "List A", "Metric": "Needs Review", "Value": summary["needs_review"]},
        {"Section": "Printer Audit", "Metric": "Printer Records", "Value": summary["printer_records"]},
        {"Section": "Printer Audit", "Metric": "Printer ISBNs", "Value": summary["printer_isbns"]},
        {
            "Section": "Printer Audit",
            "Metric": "Printer Records Not in List A",
            "Value": summary["printer_not_in_list_a"],
        },
        {
            "Section": "Printer Audit",
            "Metric": "Printer Records Without Extractable Identifier",
            "Value": summary["printer_without_isbn"],
        },
    ]

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(list_a_rows or [{"Status": ""}]).to_excel(
            writer, sheet_name="List A Reconciliation", index=False
        )
        pd.DataFrame(found or [{"Status": ""}]).to_excel(writer, sheet_name="Found", index=False)
        pd.DataFrame(not_found or [{"Status": ""}]).to_excel(
            writer, sheet_name="Not Found", index=False
        )
        pd.DataFrame(printer_audit or [{"Status": ""}]).to_excel(
            writer, sheet_name="Printer Audit", index=False
        )
        pd.DataFrame(needs_review or [{"Status": ""}]).to_excel(
            writer, sheet_name="Needs Review", index=False
        )
        pd.DataFrame(printer_raw_rows or [{"Source Row": ""}]).to_excel(
            writer, sheet_name="Printer Raw Records", index=False
        )

        # Keep List A original for ops reference
        list_a_export = []
        for rec in list_a:
            list_a_export.append(
                {
                    "Source Row": rec.source_row_number,
                    "ISBN Original": rec.isbn_original or "",
                    "ISBN Normalized": rec.isbn_normalized or "",
                    "Valid": "Yes" if rec.is_valid_isbn else "No",
                    "Date": rec.date or "",
                    "Voucher No.": rec.voucher_no or "",
                    "Party": rec.party or "",
                    "Item": rec.item or "",
                    "Unit": rec.unit or "",
                    "Pending Qty": rec.pending_qty or "",
                }
            )
        pd.DataFrame(list_a_export or [{"Source Row": ""}]).to_excel(
            writer, sheet_name="List A Original", index=False
        )

        workbook = writer.book
        text_format = workbook.add_format({"num_format": "@"})
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            ws.set_column("B:B", 18, text_format)

    buffer.seek(0)
    return buffer
