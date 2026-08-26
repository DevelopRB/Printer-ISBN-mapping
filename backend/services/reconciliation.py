"""Reconciliation engine: List A is the primary business dataset.

Primary question: for every ISBN in List A, was it found in the selected printer records?
Printer-only ISBNs are a separate audit dataset — not primary List A statuses.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from logging_config import logger
from models.models import ListARecord, Printer, PrinterRecord, Project, ReconciliationResult

# Primary List A statuses
FOUND = "FOUND"
NOT_FOUND = "NOT_FOUND"
DUPLICATE_IN_LIST_A = "DUPLICATE_IN_LIST_A"
NEEDS_REVIEW = "NEEDS_REVIEW"

# Secondary printer audit statuses
PRINTER_RECORDS_NOT_IN_LIST_A = "PRINTER_RECORDS_NOT_IN_LIST_A"
ISBN_NOT_FOUND = "ISBN_NOT_FOUND"  # printer document — identifier not extracted

# Backward-compatible aliases (older stored results / imports)
MATCHED = FOUND
NOT_REPORTED = NOT_FOUND
UNEXPECTED_PRINTER_ISBN = PRINTER_RECORDS_NOT_IN_LIST_A
INVALID_ISBN = NEEDS_REVIEW
MULTIPLE_PRINTER_OCCURRENCES = FOUND


def run_reconciliation(db: Session, project_id: int) -> dict:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("Project not found.")

    list_a = (
        db.query(ListARecord)
        .join(ListARecord.upload)
        .filter(ListARecord.upload.has(project_id=project_id))
        .all()
    )
    if not list_a:
        raise ValueError("List A was not uploaded or has no records.")

    printers = (
        db.query(Printer)
        .filter(Printer.project_id == project_id)
        .order_by(Printer.slot)
        .all()
    )
    printer_map = {p.id: p for p in printers}

    printer_records = (
        db.query(PrinterRecord)
        .join(PrinterRecord.upload)
        .filter(PrinterRecord.upload.has(project_id=project_id))
        .all()
    )
    if not printer_records:
        raise ValueError("At least one printer file must be uploaded.")

    db.query(ReconciliationResult).filter(ReconciliationResult.project_id == project_id).delete()

    by_isbn_printer: dict[str, list[PrinterRecord]] = defaultdict(list)
    no_isbn_printer: list[PrinterRecord] = []

    for pr in printer_records:
        if pr.isbn_normalized:
            by_isbn_printer[pr.isbn_normalized].append(pr)
        else:
            no_isbn_printer.append(pr)

    by_isbn_list_a: dict[str, list[ListARecord]] = defaultdict(list)
    invalid_list_a: list[ListARecord] = []

    for rec in list_a:
        if rec.isbn_normalized and rec.is_valid_isbn:
            by_isbn_list_a[rec.isbn_normalized].append(rec)
        else:
            invalid_list_a.append(rec)

    results: list[ReconciliationResult] = []
    list_a_isbns = set(by_isbn_list_a.keys())
    printer_isbns = set(by_isbn_printer.keys())

    # Primary reconciliation — List A driven (one row per List A record)
    for isbn, list_recs in by_isbn_list_a.items():
        printer_hits = by_isbn_printer.get(isbn, [])
        is_dup_list_a = len(list_recs) > 1

        for list_rec in list_recs:
            if is_dup_list_a:
                status = DUPLICATE_IN_LIST_A
            elif printer_hits:
                status = FOUND
            else:
                status = NOT_FOUND

            results.append(
                _build_result(
                    project_id=project_id,
                    isbn=isbn,
                    status=status,
                    list_recs=[list_rec],
                    printer_hits=printer_hits,
                    printer_map=printer_map,
                )
            )

    # Secondary audit — printer ISBNs not in List A (unique ISBN per row)
    for isbn in sorted(printer_isbns - list_a_isbns):
        hits = by_isbn_printer[isbn]
        results.append(
            _build_result(
                project_id=project_id,
                isbn=isbn,
                status=PRINTER_RECORDS_NOT_IN_LIST_A,
                list_recs=[],
                printer_hits=hits,
                printer_map=printer_map,
            )
        )

    # List A rows needing review (invalid / missing ISBN)
    for rec in invalid_list_a:
        results.append(
            _build_result(
                project_id=project_id,
                isbn=rec.isbn_normalized or rec.isbn_original,
                status=NEEDS_REVIEW,
                list_recs=[rec],
                printer_hits=[],
                printer_map=printer_map,
            )
        )

    # Printer documents with no extractable ISBN (audit only)
    for pr in no_isbn_printer:
        results.append(
            _build_result(
                project_id=project_id,
                isbn=None,
                status=ISBN_NOT_FOUND,
                list_recs=[],
                printer_hits=[pr],
                printer_map=printer_map,
            )
        )

    db.add_all(results)
    project.reconciled_at = datetime.now(timezone.utc)
    db.commit()

    summary = compute_summary(db, project_id)
    logger.info("Reconciliation complete for project %s: %s", project_id, summary)
    return summary


def _unique_preserve(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


def _build_result(
    project_id: int,
    isbn: str | None,
    status: str,
    list_recs: list[ListARecord],
    printer_hits: list[PrinterRecord],
    printer_map: dict[int, Printer],
    extra_flags: list[str] | None = None,  # unused; kept for call-site compatibility
) -> ReconciliationResult:
    del extra_flags  # no longer used as primary status flags
    list_rec = list_recs[0] if list_recs else None
    printer_ids = [p.printer_id for p in printer_hits]
    printer_names = []
    printer_dates = []
    original_values = []
    for p in printer_hits:
        prn = printer_map.get(p.printer_id)
        printer_names.append(prn.name if prn else f"Printer {p.printer_id}")
        printer_dates.append(p.printer_date or "")
        original_values.append(p.source_value or "")

    unique_names = _unique_preserve(printer_names)
    unique_dates = _unique_preserve(printer_dates)
    source = ", ".join(unique_names) if unique_names else None

    return ReconciliationResult(
        project_id=project_id,
        isbn=isbn,
        status=status,
        printer_ids=json.dumps(printer_ids),
        list_a_record_ids=json.dumps([r.id for r in list_recs]),
        printer_record_ids=json.dumps([p.id for p in printer_hits]),
        item=list_rec.item if list_rec else None,
        party=list_rec.party if list_rec else None,
        voucher_no=list_rec.voucher_no if list_rec else None,
        list_a_date=list_rec.date if list_rec else None,
        pending_qty=list_rec.pending_qty if list_rec else None,
        printer_names=json.dumps(unique_names),
        printer_dates=json.dumps(unique_dates),
        original_printer_values=json.dumps([v for v in original_values if v]),
        source=source,
    )


def compute_summary(db: Session, project_id: int) -> dict:
    list_a_count = (
        db.query(ListARecord)
        .join(ListARecord.upload)
        .filter(ListARecord.upload.has(project_id=project_id))
        .count()
    )
    unique_isbns = (
        db.query(ListARecord.isbn_normalized)
        .join(ListARecord.upload)
        .filter(
            ListARecord.upload.has(project_id=project_id),
            ListARecord.isbn_normalized.isnot(None),
            ListARecord.is_valid_isbn == 1,
        )
        .distinct()
        .count()
    )

    results = db.query(ReconciliationResult).filter(ReconciliationResult.project_id == project_id).all()

    def count_status(*statuses: str) -> int:
        return sum(1 for r in results if r.status in statuses)

    printer_rec_count = (
        db.query(PrinterRecord)
        .join(PrinterRecord.upload)
        .filter(PrinterRecord.upload.has(project_id=project_id))
        .count()
    )
    printer_isbn_count = (
        db.query(PrinterRecord.isbn_normalized)
        .join(PrinterRecord.upload)
        .filter(
            PrinterRecord.upload.has(project_id=project_id),
            PrinterRecord.isbn_normalized.isnot(None),
        )
        .distinct()
        .count()
    )

    found = count_status(FOUND)
    not_found = count_status(NOT_FOUND)
    duplicates = count_status(DUPLICATE_IN_LIST_A)
    needs_review = count_status(NEEDS_REVIEW)
    printer_not_in_list_a = count_status(PRINTER_RECORDS_NOT_IN_LIST_A)
    printer_without_isbn = count_status(ISBN_NOT_FOUND)

    return {
        # Primary — List A
        "list_a_records": list_a_count,
        "unique_isbns": unique_isbns,
        "found": found,
        "not_found": not_found,
        "duplicates": duplicates,
        "needs_review": needs_review,
        # Secondary — printer audit (not mixed into primary List A counts)
        "printer_records": printer_rec_count,
        "printer_isbns": printer_isbn_count,
        "printer_not_in_list_a": printer_not_in_list_a,
        "printer_without_isbn": printer_without_isbn,
        "total_results": len(results),
        # Backward-compatible keys for older UI/clients
        "matched": found,
        "not_reported": not_found,
        "unexpected": printer_not_in_list_a,
        "invalid": needs_review,
        "multiple_occurrences": 0,
        "isbn_not_found": printer_without_isbn,
    }


def get_printer_summaries(db: Session, project_id: int) -> list[dict]:
    printers = (
        db.query(Printer)
        .filter(Printer.project_id == project_id)
        .order_by(Printer.slot)
        .all()
    )
    list_a_isbns = {
        r.isbn_normalized
        for r in db.query(ListARecord)
        .join(ListARecord.upload)
        .filter(
            ListARecord.upload.has(project_id=project_id),
            ListARecord.isbn_normalized.isnot(None),
            ListARecord.is_valid_isbn == 1,
        )
        .all()
    }

    summaries = []
    for p in printers:
        records = db.query(PrinterRecord).filter(PrinterRecord.printer_id == p.id).all()
        if not records:
            continue
        extracted = [r for r in records if r.isbn_normalized]
        not_extracted = len(records) - len(extracted)
        matched = sum(1 for r in extracted if r.isbn_normalized in list_a_isbns)
        not_in_list_a = sum(1 for r in extracted if r.isbn_normalized not in list_a_isbns)
        summaries.append(
            {
                "printer_id": p.id,
                "printer_name": p.name,
                "slot": p.slot,
                "records_received": len(records),
                "isbns_extracted": len(extracted),
                "isbns_not_extracted": not_extracted,
                "matched_with_list_a": matched,
                "unexpected": not_in_list_a,
                "printer_not_in_list_a": not_in_list_a,
            }
        )
    return summaries
