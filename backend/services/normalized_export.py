"""Normalized Operations export — List A / Printer / Reconciliation / Skipped.

Uses already-processed List A from the CURRENT project/run only.

Sheet 2 (Printer ISBNs) is a LINE-BY-LINE normalized view of the downloaded
printer data (not a unique ISBN list):

  CURRENT PRINTER TSV
      → raw printer record (source order)
      → 4010 field
      → extract identifier (per document / `|` split)
      → normalize identifier
      → Sheet 2 row (same relative order; duplicates kept)

Sheet 4 (Skipped ISBNs) lists raw printer records from which no identifier
could be extracted (source order preserved).

Rules for Sheet 2:
  - Preserve source order (never sort)
  - Preserve duplicates (never set / DISTINCT / drop_duplicates / GROUP BY)
  - Skip only records with no extractable identifier (gaps do not reorder others)
  - Never use List A, prior runs, or reconciliation results as a source
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path

from sqlalchemy.orm import Session

from logging_config import logger
from models.models import (
    AutomatedPrinterRecord,
    AutomatedResult,
    AutomatedRun,
    ListARecord,
    PrinterDownload,
    PrinterRecord,
    Project,
    ReconciliationResult,
)
from services.isbn_extractor import extract_isbn, split_4010_filenames


PRESENT = "PRESENT"
NOT_FOUND = "NOT FOUND"
SKIP_REASON_NO_ISBN = "No ISBN found"


@dataclass(frozen=True)
class PrinterIsbnTrace:
    """Internal provenance for one Sheet 2 occurrence."""

    printer_record_id: str
    source_row: int
    raw_4010_value: str
    extracted_identifier: str
    normalized_identifier: str
    occurrence_index: int
    document_filename: str | None = None


@dataclass(frozen=True)
class SkippedPrinterTrace:
    """Internal provenance for one Sheet 4 skipped printer record."""

    source_row: int
    printer_record: str
    reason: str


@dataclass
class PrinterClassifyResult:
    """Outcome of classifying every raw printer record in source order."""

    extracted: list[PrinterIsbnTrace] = field(default_factory=list)
    skipped: list[SkippedPrinterTrace] = field(default_factory=list)
    raw_record_count: int = 0


def normalized_export_filename(when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    return f"Normalized_Reconciliation_{stamp}.xlsx"


def _raw_4010_from_printer_record(raw_json: str | None, fallback: str | None) -> str | None:
    """Prefer original 4010 value stored at ingest; else per-document filename."""
    if raw_json:
        try:
            data = json.loads(raw_json)
            raw = data.get("_raw_4010_value") or data.get("_original_filename")
            if raw:
                return str(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return fallback


def identifier_traceable_to_raw(isbn: str, raw_source: str | None) -> bool:
    """True iff `isbn` is extractable from the raw printer source value.

    Hyphenated forms such as Pub_978-93-6433-007-7… are valid sources for
    9789364330077 — the digits must come from that raw string via extract_isbn.
    """
    if not isbn or not raw_source:
        return False
    extracted = extract_isbn(raw_source)
    if extracted == isbn:
        return True
    for part in split_4010_filenames(raw_source):
        if extract_isbn(part) == isbn:
            return True
    return False


def classify_4010_values(
    raw_4010_values: list[str],
    *,
    source_label: str = "tsv",
) -> PrinterClassifyResult:
    """Classify each raw printer 4010 into extracted ISBN(s) and/or skipped.

    Walks values in list order. Does not sort or dedupe.

    - Each successfully extracted identifier → Sheet 2 trace
    - Raw records with zero extractable identifiers → Sheet 4 skipped row
    - Multi-document `|` fields may yield multiple Sheet 2 rows from one raw record
    """
    result = PrinterClassifyResult(raw_record_count=len(raw_4010_values))
    occurrence_index = 0

    for row_idx, raw_4010 in enumerate(raw_4010_values, start=1):
        raw = (raw_4010 or "").strip()
        if not raw:
            result.skipped.append(
                SkippedPrinterTrace(
                    source_row=row_idx,
                    printer_record="",
                    reason=SKIP_REASON_NO_ISBN,
                )
            )
            continue

        filenames = split_4010_filenames(raw) or [raw]
        extracted_this_row = 0
        for doc_i, filename in enumerate(filenames):
            extracted = extract_isbn(filename) if filename else None
            if not extracted:
                continue
            if not identifier_traceable_to_raw(extracted, raw):
                logger.warning(
                    "Skipped untraceable extract isbn=%s raw=%r",
                    extracted,
                    raw[:120],
                )
                continue
            occurrence_index += 1
            extracted_this_row += 1
            result.extracted.append(
                PrinterIsbnTrace(
                    printer_record_id=f"{source_label}:{row_idx}:{doc_i}",
                    source_row=row_idx,
                    raw_4010_value=raw,
                    extracted_identifier=extracted,
                    normalized_identifier=extracted,
                    occurrence_index=occurrence_index,
                    document_filename=filename,
                )
            )

        if extracted_this_row == 0:
            result.skipped.append(
                SkippedPrinterTrace(
                    source_row=row_idx,
                    printer_record=raw,
                    reason=SKIP_REASON_NO_ISBN,
                )
            )

    return result


def extract_traces_from_4010_values(
    raw_4010_values: list[str],
    *,
    source_label: str = "tsv",
) -> list[PrinterIsbnTrace]:
    """Canonical Sheet 2 pipeline (extracted occurrences only)."""
    return classify_4010_values(raw_4010_values, source_label=source_label).extracted


def ordered_occurrence_lists_match(manual: list[str], automated: list[str]) -> bool:
    """True iff both lists have the same length and identical values at every index."""
    return len(manual) == len(automated) and all(
        a == b for a, b in zip(manual, automated, strict=True)
    )


def collect_traced_printer_isbns(
    records: list,
    *,
    source_attr: str,
    raw_json_attr: str | None = None,
) -> list[str]:
    """Build Printer ISBN occurrence list with provenance gate (DB-record path)."""
    traces, _skipped = classify_db_printer_records(
        records,
        source_attr=source_attr,
        raw_json_attr=raw_json_attr,
    )
    return [t.normalized_identifier for t in traces]


def classify_db_printer_records(
    records: list,
    *,
    source_attr: str,
    raw_json_attr: str | None = None,
) -> tuple[list[PrinterIsbnTrace], list[SkippedPrinterTrace]]:
    """Classify DB printer rows into extracted + skipped (source order).

    Groups by source_row so multi-document expansions of one raw 4010 are one
    logical record for skip decisions.
    """
    # Group records by source row while preserving first-seen order
    groups: dict[int, list] = {}
    order: list[int] = []
    for rec in records:
        source_row = int(
            getattr(rec, "source_row", 0) or getattr(rec, "source_row_number", 0) or 0
        )
        if source_row not in groups:
            groups[source_row] = []
            order.append(source_row)
        groups[source_row].append(rec)

    extracted: list[PrinterIsbnTrace] = []
    skipped: list[SkippedPrinterTrace] = []
    occurrence_index = 0

    for source_row in order:
        group = groups[source_row]
        first = group[0]
        raw_json = getattr(first, raw_json_attr, None) if raw_json_attr else None
        fallback = getattr(first, source_attr, None)
        raw_source = _raw_4010_from_printer_record(raw_json, fallback) or ""

        row_extracted = 0
        for rec in group:
            isbn = getattr(rec, "isbn_normalized", None)
            if not isbn:
                continue
            rec_fallback = getattr(rec, source_attr, None)
            rec_raw = _raw_4010_from_printer_record(
                getattr(rec, raw_json_attr, None) if raw_json_attr else None,
                rec_fallback,
            )
            if not identifier_traceable_to_raw(isbn, rec_raw or raw_source):
                logger.warning(
                    "Normalized export dropped untraceable printer ISBN=%s raw=%r",
                    isbn,
                    (rec_raw or raw_source or "")[:120],
                )
                continue
            occurrence_index += 1
            row_extracted += 1
            rec_id = getattr(rec, "id", None)
            extracted.append(
                PrinterIsbnTrace(
                    printer_record_id=str(rec_id) if rec_id is not None else f"row:{source_row}",
                    source_row=source_row,
                    raw_4010_value=rec_raw or raw_source,
                    extracted_identifier=isbn,
                    normalized_identifier=isbn,
                    occurrence_index=occurrence_index,
                    document_filename=rec_fallback,
                )
            )

        if row_extracted == 0:
            display = raw_source or (fallback or "")
            skipped.append(
                SkippedPrinterTrace(
                    source_row=source_row if source_row else len(skipped) + 1,
                    printer_record=display,
                    reason=SKIP_REASON_NO_ISBN,
                )
            )

    _assert_every_trace_has_source(extracted)
    return extracted, skipped


def _assert_every_trace_has_source(traces: list[PrinterIsbnTrace]) -> None:
    """Hard gate: every Sheet 2 identifier must have a current-run raw source."""
    for t in traces:
        if not t.raw_4010_value or not t.normalized_identifier:
            raise AssertionError(
                f"Printer ISBN missing source lineage: id={t.printer_record_id!r} "
                f"isbn={t.normalized_identifier!r}"
            )
        if not identifier_traceable_to_raw(t.normalized_identifier, t.raw_4010_value):
            raise AssertionError(
                f"Printer ISBN not traceable to raw 4010: isbn={t.normalized_identifier!r} "
                f"raw={t.raw_4010_value[:120]!r}"
            )


def classify_tsv_bytes(tsv_bytes: bytes, *, source_label: str = "tsv") -> PrinterClassifyResult:
    """Parse a printer TSV and classify into extracted + skipped."""
    from printers.joblog_adapter import JobLogCgiAdapter

    adapter = object.__new__(JobLogCgiAdapter)
    records, _meta = JobLogCgiAdapter._parse_tsv(adapter, tsv_bytes)
    raw_values = [(r.source_filename or "") for r in records]
    return classify_4010_values(raw_values, source_label=source_label)


def printer_isbns_from_tsv_bytes(tsv_bytes: bytes, *, source_label: str = "tsv") -> list[PrinterIsbnTrace]:
    """Parse a printer TSV and extract Sheet 2 traces (current download only)."""
    return classify_tsv_bytes(tsv_bytes, source_label=source_label).extracted


def classify_run_downloads(db: Session, run_id: int) -> PrinterClassifyResult | None:
    """Classify Sheet 2/4 from this run's stored TSV download(s)."""
    downloads = (
        db.query(PrinterDownload)
        .filter(
            PrinterDownload.run_id == run_id,
            PrinterDownload.status == "COMPLETED",
        )
        .order_by(PrinterDownload.printer_slot, PrinterDownload.id)
        .all()
    )
    if not downloads:
        return None

    by_slot: dict[int, PrinterDownload] = {}
    for d in downloads:
        by_slot[d.printer_slot] = d

    merged = PrinterClassifyResult()
    for slot in sorted(by_slot):
        d = by_slot[slot]
        path = Path(d.stored_path) if d.stored_path else None
        if not path or not path.is_file():
            logger.warning(
                "Normalized export: missing TSV for run=%s slot=%s path=%s",
                run_id,
                slot,
                d.stored_path,
            )
            return None
        part = classify_tsv_bytes(
            path.read_bytes(),
            source_label=f"run{run_id}:slot{slot}:dl{d.id}",
        )
        # Offset skipped/extracted source_row is already 1-based within each TSV;
        # for multi-slot, keep per-TSV row numbers (Ops compares within each printer).
        merged.extracted.extend(part.extracted)
        merged.skipped.extend(part.skipped)
        merged.raw_record_count += part.raw_record_count
        logger.info(
            "Normalized classify TSV run=%s slot=%s raw=%s extracted=%s skipped=%s",
            run_id,
            slot,
            part.raw_record_count,
            len(part.extracted),
            len(part.skipped),
        )

    _assert_every_trace_has_source(merged.extracted)
    return merged


def printer_isbns_from_run_downloads(db: Session, run_id: int) -> list[PrinterIsbnTrace] | None:
    """Rebuild Sheet 2 strictly from this run's stored TSV download(s)."""
    result = classify_run_downloads(db, run_id)
    return None if result is None else result.extracted


def build_normalized_workbook(
    list_a_isbns: list[str],
    printer_rows: list[tuple[str, str]] | list[str],
    skipped_rows: list[tuple[int, str, str]] | None = None,
) -> BytesIO:
    """Build the 4-sheet Operations workbook.

    Sheet 1 — List A ISBNs: all List A occurrences in source order (no dedupe).
    Sheet 2 — Printer ISBNs: ordered occurrences with source filename (no dedupe).
    Sheet 3 — Reconciliation: all List A occurrences (duplicates retained) vs
              printer presence (PRESENT if ISBN appears at least once in Sheet 2).
    Sheet 4 — Skipped ISBNs: raw printer records with no extractable ISBN.

    `printer_rows` may be legacy `list[str]` (ISBN only) or
    `list[tuple[isbn, source_filename]]`.
    `skipped_rows` items are `(source_row, printer_record, reason)`.
    """
    import xlsxwriter

    # Normalize printer_rows to (isbn, filename)
    normalized_printer: list[tuple[str, str]] = []
    for item in printer_rows:
        if isinstance(item, tuple):
            isbn, filename = item[0], item[1] if len(item) > 1 else ""
            normalized_printer.append((isbn or "", filename or ""))
        else:
            normalized_printer.append((item or "", ""))

    skipped_rows = list(skipped_rows or [])

    # Presence set for status only — Sheet 3 itself keeps List A duplicates
    printer_set = {isbn for isbn, _fn in normalized_printer if isbn}
    # One reconciliation row per List A occurrence (including duplicates)
    reconciliation_list_a = [isbn for isbn in list_a_isbns if isbn]

    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True, "strings_to_numbers": False})

    header_fmt = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#1E293B",
            "font_color": "#FFFFFF",
            "border": 1,
        }
    )
    text_fmt = workbook.add_format({"num_format": "@", "border": 1})
    present_fmt = workbook.add_format(
        {
            "num_format": "@",
            "border": 1,
            "bg_color": "#DCFCE7",
            "font_color": "#166534",
            "bold": True,
        }
    )
    not_found_fmt = workbook.add_format(
        {
            "num_format": "@",
            "border": 1,
            "bg_color": "#FEF3C7",
            "font_color": "#92400E",
            "bold": True,
        }
    )

    # Sheet 1 — List A occurrence list
    ws1 = workbook.add_worksheet("List A ISBNs")
    ws1.write(0, 0, "ISBN", header_fmt)
    for i, isbn in enumerate(list_a_isbns, start=1):
        ws1.write_string(i, 0, isbn or "", text_fmt)
    _finish_sheet(ws1, max(1, len(list_a_isbns)), 1)

    # Sheet 2 — Printer ISBN occurrences + source filename
    ws2 = workbook.add_worksheet("Printer ISBNs")
    ws2.write(0, 0, "ISBN", header_fmt)
    ws2.write(0, 1, "Source Filename", header_fmt)
    for i, (isbn, filename) in enumerate(normalized_printer, start=1):
        ws2.write_string(i, 0, isbn or "", text_fmt)
        ws2.write_string(i, 1, filename or "", text_fmt)
    _finish_sheet(ws2, max(1, len(normalized_printer)), 2)
    ws2.set_column(0, 0, 22)
    ws2.set_column(1, 1, 60)

    # Sheet 3 — all List A occurrences (duplicates retained) vs printer presence
    ws3 = workbook.add_worksheet("Reconciliation")
    for col, title in enumerate(["List A ISBN", "Printer ISBN", "Status"]):
        ws3.write(0, col, title, header_fmt)

    for i, isbn in enumerate(reconciliation_list_a, start=1):
        found = isbn in printer_set
        ws3.write_string(i, 0, isbn, text_fmt)
        if found:
            ws3.write_string(i, 1, isbn, text_fmt)
            ws3.write_string(i, 2, PRESENT, present_fmt)
        else:
            ws3.write_string(i, 1, "", text_fmt)
            ws3.write_string(i, 2, NOT_FOUND, not_found_fmt)

    _finish_sheet(ws3, max(1, len(reconciliation_list_a)), 3)
    ws3.set_column(0, 0, 22)
    ws3.set_column(1, 1, 22)
    ws3.set_column(2, 2, 14)

    # Sheet 4 — Skipped ISBNs (no extractable identifier)
    ws4 = workbook.add_worksheet("Skipped ISBNs")
    for col, title in enumerate(["Source Row", "Printer Record / Filename", "Reason"]):
        ws4.write(0, col, title, header_fmt)
    for i, (source_row, printer_record, reason) in enumerate(skipped_rows, start=1):
        ws4.write_string(i, 0, str(source_row), text_fmt)
        ws4.write_string(i, 1, printer_record or "", text_fmt)
        ws4.write_string(i, 2, reason or SKIP_REASON_NO_ISBN, text_fmt)
    _finish_sheet(ws4, max(1, len(skipped_rows)), 3)
    ws4.set_column(0, 0, 12)
    ws4.set_column(1, 1, 60)
    ws4.set_column(2, 2, 18)

    workbook.close()
    buffer.seek(0)
    return buffer


def _finish_sheet(ws, data_rows: int, ncols: int) -> None:
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, data_rows, ncols - 1)
    ws.set_column(0, ncols - 1, 20)


def _printer_rows_from_traces(traces: list[PrinterIsbnTrace]) -> list[tuple[str, str]]:
    return [
        (
            t.normalized_identifier,
            t.document_filename or t.raw_4010_value or "",
        )
        for t in traces
    ]


def _skipped_rows_from_traces(skipped: list[SkippedPrinterTrace]) -> list[tuple[int, str, str]]:
    return [(s.source_row, s.printer_record, s.reason) for s in skipped]


def export_normalized_for_project(db: Session, project_id: int) -> BytesIO:
    """Manual reconciliation project → normalized workbook (current project only)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("Project not found.")
    if not project.reconciled_at:
        raise ValueError("Please complete reconciliation before exporting the normalized report.")

    list_a = (
        db.query(ListARecord)
        .join(ListARecord.upload)
        .filter(ListARecord.upload.has(project_id=project_id))
        .order_by(ListARecord.source_row_number, ListARecord.id)
        .all()
    )
    if not list_a:
        raise ValueError("Please complete reconciliation before exporting the normalized report.")

    printer_recs = (
        db.query(PrinterRecord)
        .join(PrinterRecord.upload)
        .filter(PrinterRecord.upload.has(project_id=project_id))
        .order_by(PrinterRecord.source_row_number, PrinterRecord.id)
        .all()
    )
    if not printer_recs:
        raise ValueError("Please complete reconciliation before exporting the normalized report.")

    results = (
        db.query(ReconciliationResult)
        .filter(ReconciliationResult.project_id == project_id)
        .count()
    )
    if not results:
        raise ValueError("Please complete reconciliation before exporting the normalized report.")

    list_a_isbns = [r.isbn_normalized for r in list_a if r.isbn_normalized]

    raw_4010s: list[str] = []
    seen_keys: set[tuple[int, int]] = set()
    for rec in printer_recs:
        key = (int(rec.upload_id), int(rec.source_row_number or 0))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        raw = _raw_4010_from_printer_record(rec.raw_data_json, rec.source_value)
        if raw is not None:
            raw_4010s.append(raw)

    if raw_4010s:
        classified = classify_4010_values(raw_4010s, source_label=f"project{project_id}")
        _assert_every_trace_has_source(classified.extracted)
        printer_rows = _printer_rows_from_traces(classified.extracted)
        skipped_rows = _skipped_rows_from_traces(classified.skipped)
        logger.info(
            "Normalized project=%s raw=%s extracted=%s skipped=%s",
            project_id,
            classified.raw_record_count,
            len(classified.extracted),
            len(classified.skipped),
        )
    else:
        traces, skipped = classify_db_printer_records(
            printer_recs,
            source_attr="source_value",
            raw_json_attr="raw_data_json",
        )
        printer_rows = _printer_rows_from_traces(traces)
        skipped_rows = _skipped_rows_from_traces(skipped)

    if not list_a_isbns:
        raise ValueError("No normalized List A identifiers are available for export.")
    if not printer_rows:
        raise ValueError("No normalized Printer identifiers are available for export.")

    return build_normalized_workbook(list_a_isbns, printer_rows, skipped_rows)


def export_normalized_for_run(db: Session, run_id: int) -> BytesIO:
    """Automated reconciliation run → normalized workbook (this run only)."""
    run = db.query(AutomatedRun).filter(AutomatedRun.id == run_id).first()
    if not run:
        raise ValueError("Run not found.")
    if run.status not in ("COMPLETED", "PARTIAL_SUCCESS"):
        raise ValueError("Please complete reconciliation before exporting the normalized report.")

    list_a = (
        db.query(ListARecord)
        .filter(ListARecord.upload_id == run.list_a_upload_id)
        .order_by(ListARecord.source_row_number, ListARecord.id)
        .all()
    )
    if not list_a:
        raise ValueError("Please complete reconciliation before exporting the normalized report.")

    result_count = (
        db.query(AutomatedResult).filter(AutomatedResult.run_id == run_id).count()
    )
    if not result_count:
        raise ValueError("Please complete reconciliation before exporting the normalized report.")

    list_a_isbns = [r.isbn_normalized for r in list_a if r.isbn_normalized]

    classified = classify_run_downloads(db, run_id)
    if classified is not None:
        printer_rows = _printer_rows_from_traces(classified.extracted)
        skipped_rows = _skipped_rows_from_traces(classified.skipped)
        logger.info(
            "Normalized Sheet 2/4 for run=%s extracted=%s skipped=%s raw=%s",
            run_id,
            len(classified.extracted),
            len(classified.skipped),
            classified.raw_record_count,
        )
    else:
        printer_recs = (
            db.query(AutomatedPrinterRecord)
            .filter(AutomatedPrinterRecord.run_id == run_id)
            .order_by(
                AutomatedPrinterRecord.printer_slot,
                AutomatedPrinterRecord.source_row,
                AutomatedPrinterRecord.id,
            )
            .all()
        )
        if not printer_recs:
            raise ValueError("Please complete reconciliation before exporting the normalized report.")
        logger.warning(
            "Normalized Sheet 2/4 for run=%s: TSV unavailable, using DB provenance path",
            run_id,
        )
        traces, skipped = classify_db_printer_records(
            printer_recs,
            source_attr="source_filename",
            raw_json_attr="raw_json",
        )
        printer_rows = _printer_rows_from_traces(traces)
        skipped_rows = _skipped_rows_from_traces(skipped)

    if not list_a_isbns:
        raise ValueError("No normalized List A identifiers are available for export.")
    if not printer_rows:
        raise ValueError("No normalized Printer identifiers are available for export.")

    return build_normalized_workbook(list_a_isbns, printer_rows, skipped_rows)
