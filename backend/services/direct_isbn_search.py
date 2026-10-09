"""Direct ISBN search — fetch printer records for a date range and find ISBNs.
Reuses the same JobLogCgiAdapter download/parse path and extract_isbn() as
automated reconciliation. Does NOT create reconciliation result rows or Excel.
Single and multiple search share one code path: fetch each selected printer once,
then match all requested identifiers against those records locally.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from sqlalchemy.orm import Session
from logging_config import logger
from models.models import ListARecord, Upload
from printers.joblog_adapter import build_joblog_adapter_from_config, format_yyyymmdd
from services.automated_reconciliation import _download_raw_tsv, _parse_date
from services.isbn_extractor import extract_isbn, split_4010_filenames
from services.isbn_validator import normalize_isbn_digits
from services.printer_config_service import ensure_network_printer_configs
# Practical batch size for Operations paste-from-Excel workflows.
MAX_BATCH_ISBNS = 1000

@dataclass

class DirectSearchOccurrence:
    isbn: str
    print_date: str | None
    printer_name: str
    printer_slot: int
    source_filename: str | None
    source_row: int
    job_id: str | None = None
    job_end: str | None = None
    print_start: str | None = None
    job_accept: str | None = None
    result: str | None = None
    set_number: str | None = None
    output_set: str | None = None

@dataclass

class PrinterSearchStatus:
    slot: int
    name: str
    ok: bool
    record_count: int = 0
    match_count: int = 0
    error: str | None = None

@dataclass

class DirectSearchResult:
    query: str
    normalized_isbn: str
    start_date: str
    end_date: str
    list_a: bool | None  # None = no List A loaded
    printer: bool
    status: str
    occurrences: list[DirectSearchOccurrence] = field(default_factory=list)
    printers: list[PrinterSearchStatus] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)

@dataclass

class DirectBatchItemResult:
    query: str
    normalized_isbn: str
    list_a: bool | None
    printer: bool
    status: str  # PRESENT | FOUND IN PRINTER DATA | NOT FOUND | CONNECTION ISSUE
    occurrences: list[DirectSearchOccurrence] = field(default_factory=list)

@dataclass

class DirectBatchSearchResult:
    start_date: str
    end_date: str
    entered_count: int
    unique_count: int
    found_count: int
    not_found_count: int
    connection_issue_count: int
    results: list[DirectBatchItemResult] = field(default_factory=list)
    printers: list[PrinterSearchStatus] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)

def _normalize_query(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    digits = normalize_isbn_digits(text)
    if digits:
        return digits
    # Fallback: treat free text as a filename-like value
    return extract_isbn(text)

def _resolve_status(
    list_a_flag: bool | None,
    printer_found: bool,
    *,
    any_printer_ok: bool,
    any_printer_failed: bool,
) -> str:
    if printer_found:
        if list_a_flag is True:
            return "PRESENT"
        return "FOUND IN PRINTER DATA"
    # No matches — only report NOT FOUND when we successfully searched at least
    # one printer and none failed (otherwise we cannot confidently say NOT FOUND).
    if not any_printer_ok or any_printer_failed:
        return "CONNECTION ISSUE"
    if list_a_flag is True:
        return "NOT FOUND"
    return "NOT FOUND"

def _list_a_flags(
    db: Session,
    list_a_upload_id: int | None,
    normalized_isbns: list[str],
) -> dict[str, bool | None]:
    """Map normalized ISBN → List A presence. None when no List A is loaded."""
    if list_a_upload_id is None:
        return {isbn: None for isbn in normalized_isbns}
    upload = (
        db.query(Upload)
        .filter(Upload.id == list_a_upload_id, Upload.upload_type == "list_a")
        .first()
    )
    if not upload:
        return {isbn: None for isbn in normalized_isbns}
    present: set[str] = set()
    # Chunk IN queries for large batches
    chunk_size = 400
    for i in range(0, len(normalized_isbns), chunk_size):
        chunk = normalized_isbns[i : i + chunk_size]
        rows = (
            db.query(ListARecord.isbn_normalized)
            .filter(
                ListARecord.upload_id == list_a_upload_id,
                ListARecord.isbn_normalized.in_(chunk),
            )
            .all()
        )
        present.update(r[0] for r in rows if r[0])
    return {isbn: (isbn in present) for isbn in normalized_isbns}

def _fetch_and_match_printers(
    db: Session,
    *,
    targets: set[str],
    printer_slots: list[int],
    start: date,
    end: date,
) -> tuple[list[DirectSearchOccurrence], list[PrinterSearchStatus], list[dict]]:
    """Download each selected printer once; match all target ISBNs locally.
    Printer job duplicates are never collapsed — every matching job is returned.
    """
    configs = {c.slot: c for c in ensure_network_printer_configs(db)}
    steps: list[dict] = [{"label": "Searching printers...", "status": "done"}]
    printer_statuses: list[PrinterSearchStatus] = []
    matches: list[DirectSearchOccurrence] = []
    for slot in printer_slots:
        cfg = configs.get(slot)
        name = cfg.name if cfg else f"Printer {slot}"
        steps.append({"label": f"Fetching {name}...", "status": "running", "printer_slot": slot})
        if not cfg:
            steps[-1]["status"] = "error"
            steps[-1]["detail"] = "Printer configuration not found."
            printer_statuses.append(
                PrinterSearchStatus(slot=slot, name=name, ok=False, error="Configuration not found.")
            )
            continue
        adapter = build_joblog_adapter_from_config(cfg)
        try:
            conn = adapter.connect()
            if not conn.ok:
                raise RuntimeError(conn.message)
            auth = adapter.authenticate()
            if not auth.ok:
                raise RuntimeError(auth.message)
            raw_bytes = _download_raw_tsv(adapter, start, end)
            records, _meta = adapter._parse_tsv(raw_bytes)  # noqa: SLF001
            slot_matches = 0
            for i, rec in enumerate(records, start=1):
                raw_4010 = rec.source_filename
                filenames = split_4010_filenames(raw_4010) if raw_4010 else [None]
                if not filenames:
                    filenames = [None]
                for filename in filenames:
                    extracted = extract_isbn(filename) if filename else None
                    if not extracted or extracted not in targets:
                        continue
                    slot_matches += 1
                    matches.append(
                        DirectSearchOccurrence(
                            isbn=extracted,
                            print_date=rec.printer_date,
                            printer_name=name,
                            printer_slot=slot,
                            source_filename=filename,
                            source_row=i,
                            job_id=str(rec.job_no) if rec.job_no not in (None, "") else None,
                            job_end=rec.job_end,
                            print_start=rec.print_start,
                            job_accept=rec.job_accept,
                            result=rec.result,
                            set_number=rec.set_number,
                            output_set=rec.output_set,
                        )
                    )
            steps[-1]["status"] = "done"
            steps[-1]["detail"] = f"{len(records)} jobs · {slot_matches} match(es)"
            printer_statuses.append(
                PrinterSearchStatus(
                    slot=slot,
                    name=name,
                    ok=True,
                    record_count=len(records),
                    match_count=slot_matches,
                )
            )
            logger.info(
                "Direct ISBN search slot=%s jobs=%s matches=%s targets=%s range=%s→%s",
                slot,
                len(records),
                slot_matches,
                len(targets),
                format_yyyymmdd(start),
                format_yyyymmdd(end),
            )
        except Exception as exc:
            logger.exception(
                "Direct ISBN search failed slot=%s error_type=%s",
                slot,
                type(exc).__name__,
            )
            friendly = (
                f"Unable to connect to {name}. "
                "Please check that the computer is connected to the printer network."
            )
            steps[-1]["status"] = "error"
            steps[-1]["detail"] = friendly
            printer_statuses.append(
                PrinterSearchStatus(slot=slot, name=name, ok=False, error=friendly)
            )
        finally:
            adapter.disconnect()
    steps.append({"label": "Searching printer records...", "status": "done"})
    return matches, printer_statuses, steps

def direct_search_isbns(
    db: Session,
    *,
    isbns: list[str],
    printer_slots: list[int],
    start_date: str,
    end_date: str,
    list_a_upload_id: int | None = None,
    entered_count: int | None = None,
) -> DirectBatchSearchResult:
    """Search many ISBNs against one printer-data retrieval per selected printer."""
    raw_list = [str(x).strip() for x in (isbns or []) if str(x).strip()]
    if not raw_list:
        raise ValueError("Enter at least one ISBN or identifier to search.")
    # Normalize + dedupe while preserving first-seen (input) order
    unique_normalized: list[str] = []
    query_by_normalized: dict[str, str] = {}
    seen: set[str] = set()
    for raw in raw_list:
        normalized = _normalize_query(raw)
        if not normalized:
            continue
        # Same floor as printer filename extraction (≥10 digits). Letters-only invalid.
        if len(normalized.replace("X", "").replace("x", "")) < 10:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_normalized.append(normalized)
        query_by_normalized[normalized] = raw
    if not unique_normalized:
        raise ValueError("Enter a valid ISBN, for example 9867845312345")
    if len(unique_normalized) > MAX_BATCH_ISBNS:
        raise ValueError(
            f"Please search in smaller batches. Maximum is {MAX_BATCH_ISBNS} unique ISBNs."
        )
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start > end:
        raise ValueError("From date cannot be later than To date.")
    today = date.today()
    if start > today or end > today:
        raise ValueError("Dates cannot be in the future. Please choose today or an earlier date.")
    slots = sorted({int(s) for s in printer_slots})
    if not slots or any(s not in (1, 2, 3) for s in slots):
        raise ValueError("Select at least one valid printer (1–3).")
    targets = set(unique_normalized)
    matches, printer_statuses, steps = _fetch_and_match_printers(
        db,
        targets=targets,
        printer_slots=slots,
        start=start,
        end=end,
    )
    any_ok = any(p.ok for p in printer_statuses)
    any_failed = any(not p.ok for p in printer_statuses)
    if not any_ok and printer_statuses:
        raise ValueError(
            "Could not retrieve printer records. Please check printer connectivity and try again."
        )
    # Group occurrences by ISBN — preserve printer fetch order (no job collapsing)
    by_isbn: dict[str, list[DirectSearchOccurrence]] = {isbn: [] for isbn in unique_normalized}
    for occ in matches:
        by_isbn.setdefault(occ.isbn, []).append(occ)
    list_a_map = _list_a_flags(db, list_a_upload_id, unique_normalized)
    results: list[DirectBatchItemResult] = []
    found_count = 0
    not_found_count = 0
    connection_issue_count = 0
    for normalized in unique_normalized:
        occs = by_isbn.get(normalized, [])
        printer_found = len(occs) > 0
        list_a_flag = list_a_map.get(normalized)
        status = _resolve_status(
            list_a_flag,
            printer_found,
            any_printer_ok=any_ok,
            any_printer_failed=any_failed,
        )
        if printer_found:
            found_count += 1
        elif status == "CONNECTION ISSUE":
            connection_issue_count += 1
        else:
            not_found_count += 1
        results.append(
            DirectBatchItemResult(
                query=query_by_normalized.get(normalized, normalized),
                normalized_isbn=normalized,
                list_a=list_a_flag,
                printer=printer_found,
                status=status,
                occurrences=occs,
            )
        )
    return DirectBatchSearchResult(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        entered_count=entered_count if entered_count is not None else len(raw_list),
        unique_count=len(unique_normalized),
        found_count=found_count,
        not_found_count=not_found_count,
        connection_issue_count=connection_issue_count,
        results=results,
        printers=printer_statuses,
        steps=steps,
    )

def direct_search_isbn(
    db: Session,
    *,
    isbn: str,
    printer_slots: list[int],
    start_date: str,
    end_date: str,
    list_a_upload_id: int | None = None,
) -> DirectSearchResult:
    """Search one ISBN — thin wrapper over the shared batch fetch/match path."""
    if not str(isbn or "").strip():
        raise ValueError("Enter an ISBN or identifier to search.")

    batch = direct_search_isbns(
        db,
        isbns=[isbn],
        printer_slots=printer_slots,
        start_date=start_date,
        end_date=end_date,
        list_a_upload_id=list_a_upload_id,
        entered_count=1,
    )
    item = batch.results[0]
    # Single-search preserves prior behaviour: partial printer failure still yields
    # NOT FOUND (with disconnected printers listed), not CONNECTION ISSUE.
    status = item.status
    if status == "CONNECTION ISSUE":
        status = "NOT FOUND"
    return DirectSearchResult(
        query=str(isbn).strip(),
        normalized_isbn=item.normalized_isbn,
        start_date=batch.start_date,
        end_date=batch.end_date,
        list_a=item.list_a,
        printer=item.printer,
        status=status,
        occurrences=item.occurrences,
        printers=batch.printers,
        steps=batch.steps,
    )
