"""Normalized Operations export — List A / per-printer ISBNs / Reconciliation / Skipped.

Uses already-processed List A from the CURRENT project/run only.

Printer ISBN sheets are a LINE-BY-LINE normalized view of each printer's
downloaded data (not a unique ISBN list), one sheet per printer:

  CURRENT PRINTER TSV (per printer)
      → raw printer record (source order)
      → 4010 field
      → extract identifier (per document / `|` split)
      → normalize identifier
      → Printer N ISBNs row (same relative order; duplicates kept)

Sheet Skipped ISBNs lists raw printer records from which no identifier
could be extracted (source order preserved).

Rules for printer ISBN sheets:
  - Preserve source order (never sort)
  - Preserve duplicates (never set / DISTINCT / drop_duplicates / GROUP BY)
  - Skip only records with no extractable identifier (gaps do not reorder others)
  - Never use List A, prior runs, or reconciliation results as a source
  - Never merge Printer 1 / 2 / 3 into one sheet
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
    """Internal provenance for one printer ISBN occurrence."""

    printer_record_id: str
    source_row: int
    raw_4010_value: str
    extracted_identifier: str
    normalized_identifier: str
    occurrence_index: int
    document_filename: str | None = None
    print_date: str | None = None  # ISO YYYY-MM-DD from same printer job row
    job_id: str | None = None
    printer_slot: int | None = None
    printer_name: str | None = None


@dataclass(frozen=True)
class SkippedPrinterTrace:
    """Internal provenance for one skipped printer record."""

    source_row: int
    printer_record: str
    reason: str
    print_date: str | None = None
    printer_slot: int | None = None
    printer_name: str | None = None


@dataclass
class PrinterClassifyResult:
    """Outcome of classifying every raw printer record in source order."""

    extracted: list[PrinterIsbnTrace] = field(default_factory=list)
    skipped: list[SkippedPrinterTrace] = field(default_factory=list)
    raw_record_count: int = 0


def printer_isbn_sheet_title(slot: int | None, name: str | None = None) -> str:
    """Excel sheet name for a printer ISBN sheet, e.g. 'Printer 1 ISBNs'."""
    if slot in (1, 2, 3):
        return f"Printer {slot} ISBNs"
    label = (name or "Printer").strip() or "Printer"
    # Excel sheet names max 31 chars
    title = f"{label} ISBNs"
    return title[:31]


_MONTH_ABBR = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def format_ops_date(value: str | None) -> str:
    """Display date as 27-Aug-2026 from ISO YYYY-MM-DD (or passthrough)."""
    if not value:
        return ""
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            y, m, d = int(text[0:4]), int(text[5:7]), int(text[8:10])
            return f"{d:02d}-{_MONTH_ABBR[m - 1]}-{y}"
        except (ValueError, IndexError):
            pass
    # Already ops-formatted or other
    return text


def unique_print_dates_display(dates: list[str | None]) -> str:
    """Unique print dates in first-seen order, ops-formatted, comma-separated."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in dates:
        iso = (raw or "").strip()
        if not iso or iso in seen:
            continue
        seen.add(iso)
        out.append(format_ops_date(iso))
    return ", ".join(out)


def unique_printers_display(labels: list[str | None]) -> str:
    """Unique printer labels in first-seen order, comma-separated."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in labels:
        label = (raw or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        out.append(label)
    return ", ".join(out)


def printer_label_from_sheet_title(title: str | None) -> str:
    """'Printer 1 ISBNs' → 'Printer 1'; generic 'Printer ISBNs' → ''."""
    t = (title or "").strip()
    if t.endswith(" ISBNs"):
        base = t[: -len(" ISBNs")].strip()
        if base and base.lower() != "printer":
            return base
    return ""


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
    print_dates: list[str | None] | None = None,
    job_ids: list[str | None] | None = None,
) -> PrinterClassifyResult:
    """Classify each raw printer 4010 into extracted ISBN(s) and/or skipped.

    Walks values in list order. Does not sort or dedupe.
    When print_dates/job_ids are provided they MUST be same-length and
    correspond 1:1 with each raw_4010_values row (same printer job).
    """
    result = PrinterClassifyResult(raw_record_count=len(raw_4010_values))
    occurrence_index = 0
    dates = list(print_dates) if print_dates is not None else [None] * len(raw_4010_values)
    jobs = list(job_ids) if job_ids is not None else [None] * len(raw_4010_values)
    if len(dates) != len(raw_4010_values) or len(jobs) != len(raw_4010_values):
        raise ValueError("print_dates/job_ids must align 1:1 with printer job rows")

    for row_idx, raw_4010 in enumerate(raw_4010_values, start=1):
        raw = (raw_4010 or "").strip()
        row_date = dates[row_idx - 1]
        row_job = jobs[row_idx - 1]
        if not raw:
            result.skipped.append(
                SkippedPrinterTrace(
                    source_row=row_idx,
                    printer_record="",
                    reason=SKIP_REASON_NO_ISBN,
                    print_date=row_date,
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
                    print_date=row_date,
                    job_id=str(row_job) if row_job is not None else None,
                )
            )

        if extracted_this_row == 0:
            result.skipped.append(
                SkippedPrinterTrace(
                    source_row=row_idx,
                    printer_record=raw,
                    reason=SKIP_REASON_NO_ISBN,
                    print_date=row_date,
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

    Groups by (printer_slot, source_row) so multi-document expansions of one raw
    4010 are one logical record for skip decisions, without mixing printers.
    """
    # Group records by printer + source row while preserving first-seen order
    groups: dict[tuple[int | None, int], list] = {}
    order: list[tuple[int | None, int]] = []
    for rec in records:
        source_row = int(
            getattr(rec, "source_row", 0) or getattr(rec, "source_row_number", 0) or 0
        )
        slot_raw = getattr(rec, "printer_slot", None)
        slot = int(slot_raw) if slot_raw is not None else None
        key = (slot, source_row)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(rec)

    extracted: list[PrinterIsbnTrace] = []
    skipped: list[SkippedPrinterTrace] = []
    occurrence_index = 0

    for key in order:
        slot, source_row = key
        group = groups[key]
        first = group[0]
        printer_name = getattr(first, "printer_name", None)
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
                    print_date=getattr(rec, "printer_date", None),
                    job_id=_job_id_from_raw_json(
                        getattr(rec, raw_json_attr, None) if raw_json_attr else None
                    ),
                    printer_slot=slot,
                    printer_name=printer_name or (f"Printer {slot}" if slot else None),
                )
            )

        if row_extracted == 0:
            display = raw_source or (fallback or "")
            skipped.append(
                SkippedPrinterTrace(
                    source_row=source_row if source_row else len(skipped) + 1,
                    printer_record=display,
                    reason=SKIP_REASON_NO_ISBN,
                    print_date=getattr(first, "printer_date", None),
                    printer_slot=slot,
                    printer_name=printer_name or (f"Printer {slot}" if slot else None),
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


def _job_id_from_raw_json(raw_json: str | None) -> str | None:
    if not raw_json:
        return None
    try:
        data = json.loads(raw_json)
        job = data.get("_job_id") or data.get("1122")
        return str(job) if job not in (None, "") else None
    except (json.JSONDecodeError, TypeError):
        return None


def classify_tsv_bytes(tsv_bytes: bytes, *, source_label: str = "tsv") -> PrinterClassifyResult:
    """Parse a printer TSV and classify into extracted + skipped.

    Processes each job row individually so ISBN + Print Date + Filename stay linked.
    Print Date comes from the same TSV row fields that feed the Convert CSV popup Date.
    """
    from printers.joblog_adapter import JobLogCgiAdapter

    adapter = object.__new__(JobLogCgiAdapter)
    records, _meta = JobLogCgiAdapter._parse_tsv(adapter, tsv_bytes)
    raw_values = [(r.source_filename or "") for r in records]
    print_dates = [r.printer_date for r in records]
    job_ids = [r.job_no for r in records]
    return classify_4010_values(
        raw_values,
        source_label=source_label,
        print_dates=print_dates,
        job_ids=job_ids,
    )


def printer_isbns_from_tsv_bytes(tsv_bytes: bytes, *, source_label: str = "tsv") -> list[PrinterIsbnTrace]:
    """Parse a printer TSV and extract Sheet 2 traces (current download only)."""
    return classify_tsv_bytes(tsv_bytes, source_label=source_label).extracted


def _tag_classify_result(
    part: PrinterClassifyResult,
    *,
    printer_slot: int | None,
    printer_name: str | None,
) -> PrinterClassifyResult:
    """Attach printer identity to every extracted/skipped row (same-job provenance)."""
    tagged = PrinterClassifyResult(raw_record_count=part.raw_record_count)
    for t in part.extracted:
        tagged.extracted.append(
            PrinterIsbnTrace(
                printer_record_id=t.printer_record_id,
                source_row=t.source_row,
                raw_4010_value=t.raw_4010_value,
                extracted_identifier=t.extracted_identifier,
                normalized_identifier=t.normalized_identifier,
                occurrence_index=t.occurrence_index,
                document_filename=t.document_filename,
                print_date=t.print_date,
                job_id=t.job_id,
                printer_slot=printer_slot,
                printer_name=printer_name,
            )
        )
    for s in part.skipped:
        tagged.skipped.append(
            SkippedPrinterTrace(
                source_row=s.source_row,
                printer_record=s.printer_record,
                reason=s.reason,
                print_date=s.print_date,
                printer_slot=printer_slot,
                printer_name=printer_name,
            )
        )
    return tagged


def classify_run_downloads(db: Session, run_id: int) -> PrinterClassifyResult | None:
    """Classify printer ISBN sheets from this run's stored TSV download(s)."""
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
        tagged = _tag_classify_result(
            part,
            printer_slot=slot,
            printer_name=d.printer_name or f"Printer {slot}",
        )
        # Per-TSV row numbers kept; multi-slot data stays separated by printer_slot.
        merged.extracted.extend(tagged.extracted)
        merged.skipped.extend(tagged.skipped)
        merged.raw_record_count += tagged.raw_record_count
        logger.info(
            "Normalized classify TSV run=%s slot=%s raw=%s extracted=%s skipped=%s",
            run_id,
            slot,
            tagged.raw_record_count,
            len(tagged.extracted),
            len(tagged.skipped),
        )

    _assert_every_trace_has_source(merged.extracted)
    return merged


def printer_isbns_from_run_downloads(db: Session, run_id: int) -> list[PrinterIsbnTrace] | None:
    """Rebuild Sheet 2 strictly from this run's stored TSV download(s)."""
    result = classify_run_downloads(db, run_id)
    return None if result is None else result.extracted


def build_normalized_workbook(
    list_a_isbns: list[str],
    printer_rows: list[tuple[str, str, str]] | list[tuple[str, str]] | list[str] | None = None,
    skipped_rows: list[tuple[int, str, str]] | None = None,
    printer_sheets: list[tuple[str, list]] | None = None,
) -> BytesIO:
    """Build the Operations normalized workbook.

    Sheet 1 — List A ISBNs: all List A occurrences in source order (no dedupe).
    Then one sheet per printer used in the run:
      Printer 1 ISBNs / Printer 2 ISBNs / Printer 3 ISBNs
      Columns: ISBN | Print Date | Source Filename (duplicates + source order kept).
    Then Reconciliation: one row per List A occurrence (duplicates kept).
      Columns: List A ISBN | Printer ISBN | Print Date | Printer | Status
    Then Skipped ISBNs: raw printer records with no extractable ISBN.

    Pass either:
      - printer_sheets: [(sheet_title, rows), ...] preferred for multi-printer runs
      - printer_rows: flat list → single sheet titled "Printer ISBNs" (legacy/tests)

    Row shape: (isbn, print_date, filename) or (isbn, print_date, filename, printer_label).
    """
    import xlsxwriter

    def _normalize_row(item) -> tuple[str, str, str, str]:
        if isinstance(item, tuple):
            if len(item) >= 4:
                return (item[0] or "", item[1] or "", item[2] or "", item[3] or "")
            if len(item) >= 3:
                return (item[0] or "", item[1] or "", item[2] or "", "")
            if len(item) == 2:
                return (item[0] or "", "", item[1] or "", "")
            return ((item[0] if item else "") or "", "", "", "")
        return (item or "", "", "", "")

    sheets: list[tuple[str, list[tuple[str, str, str, str]]]] = []
    if printer_sheets:
        for title, rows in printer_sheets:
            sheets.append((title, [_normalize_row(r) for r in rows]))
    elif printer_rows is not None:
        sheets.append(("Printer ISBNs", [_normalize_row(r) for r in printer_rows]))

    skipped_rows = list(skipped_rows or [])

    all_printer_rows: list[tuple[str, str, str, str]] = []
    for title, rows in sheets:
        sheet_label = printer_label_from_sheet_title(title)
        for isbn, print_date, filename, row_printer in rows:
            label = (row_printer or sheet_label or "").strip()
            all_printer_rows.append((isbn, print_date, filename, label))

    printer_set = {isbn for isbn, _d, _fn, _p in all_printer_rows if isbn}
    dates_by_isbn: dict[str, list[str]] = {}
    printers_by_isbn: dict[str, list[str]] = {}
    for isbn, print_date, _fn, printer_label in all_printer_rows:
        if not isbn:
            continue
        dates_by_isbn.setdefault(isbn, []).append(print_date)
        if printer_label:
            printers_by_isbn.setdefault(isbn, []).append(printer_label)

    reconciliation_list_a = [isbn for isbn in list_a_isbns if isbn]

    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True, "strings_to_numbers": False})

    header_fmt = workbook.add_format(
        {"bold": True, "bg_color": "#1E293B", "font_color": "#FFFFFF", "border": 1}
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

    ws1 = workbook.add_worksheet("List A ISBNs")
    ws1.write(0, 0, "ISBN", header_fmt)
    for i, isbn in enumerate(list_a_isbns, start=1):
        ws1.write_string(i, 0, isbn or "", text_fmt)
    _finish_sheet(ws1, max(1, len(list_a_isbns)), 1)

    for sheet_title, rows in sheets:
        ws = workbook.add_worksheet(sheet_title[:31])
        for col, title in enumerate(["ISBN", "Print Date", "Source Filename"]):
            ws.write(0, col, title, header_fmt)
        for i, (isbn, print_date, filename, _printer) in enumerate(rows, start=1):
            ws.write_string(i, 0, isbn or "", text_fmt)
            ws.write_string(i, 1, format_ops_date(print_date), text_fmt)
            ws.write_string(i, 2, filename or "", text_fmt)
        _finish_sheet(ws, max(1, len(rows)), 3)
        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 16)
        ws.set_column(2, 2, 60)

    ws_recon = workbook.add_worksheet("Reconciliation")
    for col, title in enumerate(
        ["List A ISBN", "Printer ISBN", "Print Date", "Printer", "Status"]
    ):
        ws_recon.write(0, col, title, header_fmt)
    for i, isbn in enumerate(reconciliation_list_a, start=1):
        found = isbn in printer_set
        ws_recon.write_string(i, 0, isbn, text_fmt)
        if found:
            ws_recon.write_string(i, 1, isbn, text_fmt)
            ws_recon.write_string(
                i,
                2,
                unique_print_dates_display(dates_by_isbn.get(isbn, [])),
                text_fmt,
            )
            ws_recon.write_string(
                i,
                3,
                unique_printers_display(printers_by_isbn.get(isbn, [])),
                text_fmt,
            )
            ws_recon.write_string(i, 4, PRESENT, present_fmt)
        else:
            ws_recon.write_string(i, 1, "", text_fmt)
            ws_recon.write_string(i, 2, "", text_fmt)
            ws_recon.write_string(i, 3, "", text_fmt)
            ws_recon.write_string(i, 4, NOT_FOUND, not_found_fmt)
    _finish_sheet(ws_recon, max(1, len(reconciliation_list_a)), 5)
    ws_recon.set_column(0, 0, 22)
    ws_recon.set_column(1, 1, 22)
    ws_recon.set_column(2, 2, 28)
    ws_recon.set_column(3, 3, 28)
    ws_recon.set_column(4, 4, 14)

    # Skipped rows may be (source_row, record, reason) or
    # (source_row, record, reason, printer_label)
    has_printer_col = any(isinstance(s, tuple) and len(s) >= 4 and s[3] for s in skipped_rows)

    ws_skip = workbook.add_worksheet("Skipped ISBNs")
    if has_printer_col:
        headers = ["Printer", "Source Row", "Printer Record / Filename", "Reason"]
    else:
        headers = ["Source Row", "Printer Record / Filename", "Reason"]
    for col, title in enumerate(headers):
        ws_skip.write(0, col, title, header_fmt)
    for i, row in enumerate(skipped_rows, start=1):
        if has_printer_col:
            source_row, printer_record, reason, printer_label = (
                row[0],
                row[1],
                row[2],
                row[3] if len(row) > 3 else "",
            )
            ws_skip.write_string(i, 0, str(printer_label or ""), text_fmt)
            ws_skip.write_string(i, 1, str(source_row), text_fmt)
            ws_skip.write_string(i, 2, printer_record or "", text_fmt)
            ws_skip.write_string(i, 3, reason or SKIP_REASON_NO_ISBN, text_fmt)
        else:
            source_row, printer_record, reason = row[0], row[1], row[2]
            ws_skip.write_string(i, 0, str(source_row), text_fmt)
            ws_skip.write_string(i, 1, printer_record or "", text_fmt)
            ws_skip.write_string(i, 2, reason or SKIP_REASON_NO_ISBN, text_fmt)
    ncols = 4 if has_printer_col else 3
    _finish_sheet(ws_skip, max(1, len(skipped_rows)), ncols)
    if has_printer_col:
        ws_skip.set_column(0, 0, 14)
        ws_skip.set_column(1, 1, 12)
        ws_skip.set_column(2, 2, 60)
        ws_skip.set_column(3, 3, 18)
    else:
        ws_skip.set_column(0, 0, 12)
        ws_skip.set_column(1, 1, 60)
        ws_skip.set_column(2, 2, 18)

    workbook.close()
    buffer.seek(0)
    return buffer


def _finish_sheet(ws, data_rows: int, ncols: int) -> None:
    """Freeze below the column header; autofilter covers header + data."""
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, max(1, data_rows), ncols - 1)
    ws.set_column(0, ncols - 1, 20)


def _printer_rows_from_traces(
    traces: list[PrinterIsbnTrace],
) -> list[tuple[str, str, str, str]]:
    """(isbn, print_date_iso, source_filename, printer_label) per occurrence."""
    return [
        (
            t.normalized_identifier,
            t.print_date or "",
            t.document_filename or t.raw_4010_value or "",
            t.printer_name
            or (f"Printer {t.printer_slot}" if t.printer_slot in (1, 2, 3) else ""),
        )
        for t in traces
    ]


def _printer_sheets_from_traces(
    traces: list[PrinterIsbnTrace],
) -> list[tuple[str, list[tuple[str, str, str, str]]]]:
    """Group traces into ordered per-printer sheets."""
    by_slot: dict[int, list[PrinterIsbnTrace]] = {}
    unnamed: list[PrinterIsbnTrace] = []
    for t in traces:
        if t.printer_slot in (1, 2, 3):
            by_slot.setdefault(int(t.printer_slot), []).append(t)
        else:
            unnamed.append(t)

    sheets: list[tuple[str, list[tuple[str, str, str, str]]]] = []
    for slot in sorted(by_slot):
        sample = by_slot[slot][0]
        title = printer_isbn_sheet_title(slot, sample.printer_name)
        sheets.append((title, _printer_rows_from_traces(by_slot[slot])))
    if unnamed:
        sheets.append(("Printer ISBNs", _printer_rows_from_traces(unnamed)))
    return sheets


def _skipped_rows_from_traces(
    skipped: list[SkippedPrinterTrace],
) -> list[tuple]:
    """Skipped rows; include printer label when more than one printer is present."""
    distinct_slots = {s.printer_slot for s in skipped if s.printer_slot is not None}
    use_printer_col = len(distinct_slots) > 1
    if use_printer_col:
        return [
            (
                s.source_row,
                s.printer_record,
                s.reason,
                s.printer_name or (f"Printer {s.printer_slot}" if s.printer_slot else ""),
            )
            for s in skipped
        ]
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

    from models.models import Printer

    printers = {
        p.id: p
        for p in db.query(Printer).filter(Printer.project_id == project_id).all()
    }

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

    # Attach slot/name so sheets can be split per printer
    for rec in printer_recs:
        p = printers.get(rec.printer_id)
        if p is not None:
            setattr(rec, "printer_slot", p.slot)
            setattr(rec, "printer_name", p.name or f"Printer {p.slot}")

    traces, skipped = classify_db_printer_records(
        printer_recs,
        source_attr="source_value",
        raw_json_attr="raw_data_json",
    )
    printer_sheets = _printer_sheets_from_traces(traces)
    skipped_rows = _skipped_rows_from_traces(skipped)
    logger.info(
        "Normalized project=%s extracted=%s skipped=%s sheets=%s",
        project_id,
        len(traces),
        len(skipped),
        [t for t, _ in printer_sheets],
    )

    if not list_a_isbns:
        raise ValueError("No normalized List A identifiers are available for export.")
    if not printer_sheets or not any(rows for _, rows in printer_sheets):
        raise ValueError("No normalized Printer identifiers are available for export.")

    return build_normalized_workbook(
        list_a_isbns,
        skipped_rows=skipped_rows,
        printer_sheets=printer_sheets,
    )


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
        traces = classified.extracted
        skipped = classified.skipped
        logger.info(
            "Normalized printer sheets for run=%s extracted=%s skipped=%s raw=%s",
            run_id,
            len(traces),
            len(skipped),
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
            "Normalized printer sheets for run=%s: TSV unavailable, using DB provenance path",
            run_id,
        )
        traces, skipped = classify_db_printer_records(
            printer_recs,
            source_attr="source_filename",
            raw_json_attr="raw_json",
        )

    printer_sheets = _printer_sheets_from_traces(traces)
    skipped_rows = _skipped_rows_from_traces(skipped)

    if not list_a_isbns:
        raise ValueError("No normalized List A identifiers are available for export.")
    if not printer_sheets or not any(rows for _, rows in printer_sheets):
        raise ValueError("No normalized Printer identifiers are available for export.")

    return build_normalized_workbook(
        list_a_isbns,
        skipped_rows=skipped_rows,
        printer_sheets=printer_sheets,
    )
