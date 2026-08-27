"""Automated printer fetch + reconciliation (Phase 2D).

Uses existing JobLogCgiAdapter (cmd=dl, rs/re=YYYYMMDD). Does not invent protocol params.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from database import PRINTER_DOWNLOADS_DIR, SessionLocal
from logging_config import logger
from models.models import (
    AutomatedPrinterRecord,
    AutomatedResult,
    AutomatedRun,
    ListARecord,
    NetworkPrinterConfig,
    PrinterDownload,
    Upload,
)
from printers.joblog_adapter import build_joblog_adapter_from_config, format_yyyymmdd
from services.isbn_extractor import extract_isbn, split_4010_filenames
from services.printer_config_service import ensure_network_printer_configs
from services.reconciliation import (
    DUPLICATE_IN_LIST_A,
    FOUND,
    ISBN_NOT_FOUND,
    NEEDS_REVIEW,
    NOT_FOUND,
    PRINTER_RECORDS_NOT_IN_LIST_A,
)

STEP_DEFS = [
    ("prepare_list_a", "Preparing List A"),
    ("connect", "Connect to Printer"),
    ("authenticate", "Sign in to printer"),
    ("fetch", "Request printer data"),
    ("download", "Download Printer Data"),
    ("process", "Process printer records"),
    ("extract", "Extract ISBNs"),
    ("match", "Reconcile"),
    ("generate", "Generate results"),
    ("complete", "Complete"),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value.strip())


def _steps_payload(steps: list[dict]) -> str:
    return json.dumps(steps, ensure_ascii=False)


def _init_steps(printer_slots: list[int], printer_names: dict[int, str]) -> list[dict]:
    steps = [
        {"key": "prepare_list_a", "label": "Preparing List A", "status": "pending", "detail": None}
    ]
    for slot in printer_slots:
        name = printer_names.get(slot, f"Printer {slot}")
        for key, label in [
            ("connect", f"Connecting to {name}"),
            ("authenticate", f"Authenticating {name}"),
            ("fetch", f"Fetching job log ({name})"),
            ("download", f"Downloading printer data ({name})"),
            ("process", f"Processing records ({name})"),
        ]:
            steps.append(
                {
                    "key": f"{key}_{slot}",
                    "label": label,
                    "status": "pending",
                    "detail": None,
                    "printer_slot": slot,
                }
            )
    steps.extend(
        [
            {"key": "extract", "label": "Extracting ISBNs", "status": "pending", "detail": None},
            {"key": "match", "label": "Matching ISBNs", "status": "pending", "detail": None},
            {"key": "generate", "label": "Generating results", "status": "pending", "detail": None},
            {"key": "complete", "label": "Complete", "status": "pending", "detail": None},
        ]
    )
    return steps


def _set_step(db: Session, run: AutomatedRun, key: str, status: str, detail: str | None = None):
    steps = json.loads(run.steps_json or "[]")
    for step in steps:
        if step.get("key") == key:
            step["status"] = status
            if detail is not None:
                step["detail"] = detail
            break
    run.steps_json = _steps_payload(steps)
    db.commit()


def create_run(
    db: Session,
    *,
    list_a_upload_id: int,
    printer_slots: list[int],
    start_date: str,
    end_date: str,
) -> AutomatedRun:
    upload = db.query(Upload).filter(Upload.id == list_a_upload_id, Upload.upload_type == "list_a").first()
    if not upload:
        raise ValueError("List A upload not found.")

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start > end:
        raise ValueError("From date must be less than or equal to To date.")
    today = date.today()
    if start > today or end > today:
        raise ValueError("Dates cannot be in the future. Please choose today or an earlier date.")

    slots = sorted({int(s) for s in printer_slots})
    if not slots or any(s not in (1, 2, 3) for s in slots):
        raise ValueError("Select at least one valid printer (1–3).")

    configs = ensure_network_printer_configs(db)
    names = {c.slot: c.name for c in configs}
    steps = _init_steps(slots, names)

    run = AutomatedRun(
        list_a_upload_id=list_a_upload_id,
        printer_slots_json=json.dumps(slots),
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        status="PENDING",
        steps_json=_steps_payload(steps),
        started_at=_utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def execute_run(run_id: int) -> None:
    """Background worker entrypoint — opens its own DB session."""
    db = SessionLocal()
    try:
        run = db.query(AutomatedRun).filter(AutomatedRun.id == run_id).first()
        if not run:
            return
        run.status = "RUNNING"
        db.commit()
        _execute_run_body(db, run)
    except Exception as exc:
        logger.exception("Automated run %s failed", run_id)
        run = db.query(AutomatedRun).filter(AutomatedRun.id == run_id).first()
        if run:
            run.status = "FAILED"
            run.error_message = "Automated reconciliation failed. Check application logs."
            run.completed_at = _utcnow()
            _set_step(db, run, "complete", "error", str(type(exc).__name__))
            db.commit()
    finally:
        db.close()


def _execute_run_body(db: Session, run: AutomatedRun) -> None:
    slots = json.loads(run.printer_slots_json)
    start = _parse_date(run.start_date)
    end = _parse_date(run.end_date)

    # 1) List A
    _set_step(db, run, "prepare_list_a", "running")
    list_a = (
        db.query(ListARecord).filter(ListARecord.upload_id == run.list_a_upload_id).all()
    )
    if not list_a:
        raise ValueError("List A has no records.")
    upload = db.query(Upload).filter(Upload.id == run.list_a_upload_id).first()
    _set_step(
        db,
        run,
        "prepare_list_a",
        "done",
        f"{len(list_a)} records · {upload.isbn_detected_count if upload else 0} ISBNs",
    )

    configs = {c.slot: c for c in ensure_network_printer_configs(db)}
    printer_ok = 0
    printer_fail = 0
    all_records: list[AutomatedPrinterRecord] = []

    # Current-run isolation: never append to a previous printer dataset for this run
    existing = (
        db.query(AutomatedPrinterRecord)
        .filter(AutomatedPrinterRecord.run_id == run.id)
        .delete(synchronize_session=False)
    )
    if existing:
        logger.info(
            "Cleared %s prior automated_printer_records for run=%s before fresh ingest",
            existing,
            run.id,
        )
        db.commit()

    for slot in slots:
        cfg = configs.get(slot)
        if not cfg:
            printer_fail += 1
            continue
        name = cfg.name
        download = PrinterDownload(
            run_id=run.id,
            printer_slot=slot,
            printer_name=name,
            start_date=run.start_date,
            end_date=run.end_date,
            status="PENDING",
        )
        db.add(download)
        db.commit()
        db.refresh(download)

        adapter = build_joblog_adapter_from_config(cfg)
        try:
            _set_step(db, run, f"connect_{slot}", "running")
            conn = adapter.connect()
            if not conn.ok:
                raise RuntimeError(conn.message)
            _set_step(db, run, f"connect_{slot}", "done", conn.message)

            _set_step(db, run, f"authenticate_{slot}", "running")
            auth = adapter.authenticate()
            if not auth.ok:
                raise RuntimeError(auth.message)
            _set_step(db, run, f"authenticate_{slot}", "done", auth.message)

            _set_step(db, run, f"fetch_{slot}", "running")
            _set_step(db, run, f"download_{slot}", "running")
            # Canonical path: cmd=dl with rs/re (confirmed Phase 2C) — single download
            raw_bytes = _download_raw_tsv(adapter, start, end)
            records, meta = adapter._parse_tsv(raw_bytes)  # noqa: SLF001

            stamp = _utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"printer_{slot}_{format_yyyymmdd(start)}_{format_yyyymmdd(end)}_{stamp}.tsv"
            path = PRINTER_DOWNLOADS_DIR / filename
            path.write_bytes(raw_bytes)

            download.filename = filename
            download.stored_path = str(path)
            download.retrieved_at = _utcnow()
            download.file_size = len(raw_bytes)
            download.record_count = len(records)
            download.status = "EMPTY" if not records else "COMPLETED"
            db.commit()

            _set_step(db, run, f"fetch_{slot}", "done", f"{len(records)} jobs")
            _set_step(db, run, f"download_{slot}", "done", f"{download.file_size:,} bytes")

            _set_step(db, run, f"process_{slot}", "running")
            docs_stored = 0
            for i, rec in enumerate(records, start=1):
                raw_4010 = rec.source_filename
                filenames = split_4010_filenames(raw_4010) if raw_4010 else [None]
                if not filenames:
                    filenames = [None]

                for filename in filenames:
                    isbn = extract_isbn(filename) if filename else None
                    status = None if isbn else ISBN_NOT_FOUND
                    raw_payload = dict(rec.raw_fields) if rec.raw_fields else {}
                    raw_payload["_raw_4010_value"] = raw_4010
                    raw_payload["_original_filename"] = filename
                    raw_payload["_job_id"] = rec.job_no
                    raw_payload["_print_date"] = rec.printer_date
                    row = AutomatedPrinterRecord(
                        run_id=run.id,
                        download_id=download.id,
                        printer_slot=slot,
                        printer_name=name,
                        source_row=i,
                        source_filename=filename,
                        isbn_normalized=isbn,
                        is_valid_isbn=1 if isbn else 0,
                        printer_date=rec.printer_date,
                        status=status,
                        raw_json=json.dumps(raw_payload, ensure_ascii=False),
                    )
                    db.add(row)
                    all_records.append(row)
                    docs_stored += 1
            db.commit()
            _set_step(
                db,
                run,
                f"process_{slot}",
                "done",
                "No jobs found for selected date range."
                if not records
                else f"{len(records)} jobs → {docs_stored} documents",
            )
            printer_ok += 1
        except Exception as exc:
            logger.exception(
                "Printer fetch failed run=%s slot=%s error_type=%s",
                run.id,
                slot,
                type(exc).__name__,
            )
            friendly = (
                f"Unable to connect to {name}. "
                "Please check that the computer is connected to the printer network."
            )
            download.status = "FAILED"
            download.error_message = friendly
            db.commit()
            for key in ("connect", "authenticate", "fetch", "download", "process"):
                step_key = f"{key}_{slot}"
                steps = json.loads(run.steps_json)
                for s in steps:
                    if s.get("key") == step_key and s.get("status") == "running":
                        s["status"] = "error"
                        s["detail"] = friendly
                # also mark remaining pending for this printer as skipped
                for s in steps:
                    if s.get("printer_slot") == slot and s.get("status") == "pending":
                        s["status"] = "skipped"
                run.steps_json = _steps_payload(steps)
            db.commit()
            printer_fail += 1
        finally:
            adapter.disconnect()

    # Refresh records from DB
    all_records = (
        db.query(AutomatedPrinterRecord).filter(AutomatedPrinterRecord.run_id == run.id).all()
    )

    _set_step(db, run, "extract", "running")
    valid_isbns = sum(1 for r in all_records if r.isbn_normalized)
    invalid = sum(1 for r in all_records if not r.isbn_normalized)
    _set_step(db, run, "extract", "done", f"{valid_isbns} valid · {invalid} without ISBN")

    _set_step(db, run, "match", "running")
    results = _reconcile(list_a, all_records)
    _set_step(db, run, "match", "done", f"{len(results)} result rows")

    _set_step(db, run, "generate", "running")
    for row in results:
        db.add(
            AutomatedResult(
                run_id=run.id,
                isbn=row["isbn"],
                status=row["status"],
                item=row.get("item"),
                party=row.get("party"),
                voucher_no=row.get("voucher_no"),
                list_a_date=row.get("list_a_date"),
                pending_qty=row.get("pending_qty"),
                printer_names=json.dumps(row.get("printer_names") or []),
                printer_dates=json.dumps(row.get("printer_dates") or []),
                original_printer_values=json.dumps(row.get("original_printer_values") or []),
                list_a_record_ids=json.dumps(row.get("list_a_record_ids") or []),
                printer_record_ids=json.dumps(row.get("printer_record_ids") or []),
                source=row.get("source"),
            )
        )
    summary = _summarize(list_a, all_records, results, printer_ok, printer_fail, slots)
    run.summary_json = json.dumps(summary, ensure_ascii=False)
    db.commit()
    _set_step(db, run, "generate", "done")

    if printer_fail and printer_ok:
        run.status = "PARTIAL_SUCCESS"
    elif printer_fail and not printer_ok:
        run.status = "FAILED"
        run.error_message = "All selected printers failed."
    else:
        run.status = "COMPLETED"

    run.completed_at = _utcnow()
    _set_step(db, run, "complete", "done", run.status)
    db.commit()
    logger.info("Automated run %s finished status=%s summary=%s", run.id, run.status, summary)


def _download_raw_tsv(adapter, start: date, end: date) -> bytes:
    """Re-issue cmd=dl and return raw bytes for audit storage."""
    client = adapter._ensure_client()  # noqa: SLF001
    rs = format_yyyymmdd(start)
    re_ = format_yyyymmdd(end)
    response = client.post(
        adapter.joblog_path,
        data=adapter._form_data(cmd="dl", rs=rs, re_=re_),  # noqa: SLF001
    )
    response.raise_for_status()
    return response.content


def _reconcile(
    list_a: list[ListARecord],
    printer_recs: list[AutomatedPrinterRecord],
) -> list[dict]:
    by_isbn_printer: dict[str, list[AutomatedPrinterRecord]] = defaultdict(list)
    no_isbn: list[AutomatedPrinterRecord] = []
    for pr in printer_recs:
        if pr.isbn_normalized:
            by_isbn_printer[pr.isbn_normalized].append(pr)
        else:
            no_isbn.append(pr)

    by_isbn_list: dict[str, list[ListARecord]] = defaultdict(list)
    invalid_list: list[ListARecord] = []
    for rec in list_a:
        if rec.isbn_normalized and rec.is_valid_isbn:
            by_isbn_list[rec.isbn_normalized].append(rec)
        else:
            invalid_list.append(rec)

    results: list[dict] = []
    list_isbns = set(by_isbn_list.keys())
    printer_isbns = set(by_isbn_printer.keys())

    # Primary — List A driven
    for isbn, list_recs in by_isbn_list.items():
        hits = by_isbn_printer.get(isbn, [])
        is_dup = len(list_recs) > 1
        for list_rec in list_recs:
            if is_dup:
                status = DUPLICATE_IN_LIST_A
            elif hits:
                status = FOUND
            else:
                status = NOT_FOUND
            results.append(_row(isbn, status, [list_rec], hits))

    # Secondary audit — printer ISBNs not in List A
    for isbn in sorted(printer_isbns - list_isbns):
        results.append(
            _row(isbn, PRINTER_RECORDS_NOT_IN_LIST_A, [], by_isbn_printer[isbn])
        )

    for rec in invalid_list:
        results.append(
            _row(rec.isbn_normalized or rec.isbn_original, NEEDS_REVIEW, [rec], [])
        )

    for pr in no_isbn:
        results.append(
            {
                "isbn": None,
                "status": ISBN_NOT_FOUND,
                "item": None,
                "party": None,
                "voucher_no": None,
                "list_a_date": None,
                "pending_qty": None,
                "printer_names": [pr.printer_name],
                "printer_dates": [pr.printer_date or ""] if pr.printer_date else [],
                "original_printer_values": [pr.source_filename or ""],
                "list_a_record_ids": [],
                "printer_record_ids": [pr.id],
                "source": pr.printer_name,
                "printer_occurrences": 1,
            }
        )
    return results


def _row(
    isbn: str | None,
    status: str,
    list_recs: list[ListARecord],
    hits: list[AutomatedPrinterRecord],
) -> dict:
    list_rec = list_recs[0] if list_recs else None
    names = list(dict.fromkeys(h.printer_name for h in hits))
    dates = list(dict.fromkeys(h.printer_date or "" for h in hits if h.printer_date))
    originals = [h.source_filename or "" for h in hits if h.source_filename]
    return {
        "isbn": isbn,
        "status": status,
        "item": list_rec.item if list_rec else None,
        "party": list_rec.party if list_rec else None,
        "voucher_no": list_rec.voucher_no if list_rec else None,
        "list_a_date": list_rec.date if list_rec else None,
        "pending_qty": list_rec.pending_qty if list_rec else None,
        "printer_names": names,
        "printer_dates": dates,
        "original_printer_values": originals,
        "list_a_record_ids": [r.id for r in list_recs],
        "printer_record_ids": [h.id for h in hits],
        "source": ", ".join(names) if names else None,
        "printer_occurrences": len(hits),
    }


def _summarize(list_a, printer_recs, results, printer_ok, printer_fail, slots) -> dict:
    def count_status(*names: str) -> int:
        return sum(1 for r in results if r["status"] in names)

    unique_list = len({r.isbn_normalized for r in list_a if r.isbn_normalized and r.is_valid_isbn})
    printer_isbns = len({r.isbn_normalized for r in printer_recs if r.isbn_normalized})
    found = count_status(FOUND)
    not_found = count_status(NOT_FOUND)
    duplicates = count_status(DUPLICATE_IN_LIST_A)
    needs_review = count_status(NEEDS_REVIEW)
    printer_not_in_list_a = count_status(PRINTER_RECORDS_NOT_IN_LIST_A)
    printer_without_isbn = count_status(ISBN_NOT_FOUND)

    return {
        # Primary — List A
        "list_a_records": len(list_a),
        "unique_isbns": unique_list,
        "found": found,
        "not_found": not_found,
        "duplicates": duplicates,
        "needs_review": needs_review,
        # Secondary — printer audit
        "printer_records": len(printer_recs),
        "printer_isbns": printer_isbns,
        "valid_isbns": printer_isbns,
        "printer_not_in_list_a": printer_not_in_list_a,
        "printer_without_isbn": printer_without_isbn,
        "printers_ok": printer_ok,
        "printers_failed": printer_fail,
        "printer_slots": slots,
        # Backward-compatible keys
        "matched": found,
        "not_reported": not_found,
        "unexpected": printer_not_in_list_a,
        "multiple_occurrences": 0,
    }
