"""Automated reconciliation API (Phase 2D)."""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.schemas import (
    AutomatedRunCreate,
    AutomatedRunOut,
    AutomatedResultOut,
    DirectBatchItemOut,
    DirectIsbnSearchCreate,
    DirectIsbnSearchOut,
    DirectMultiIsbnSearchCreate,
    DirectMultiIsbnSearchOut,
    DirectSearchPrinterStatusOut,
    PaginatedAutomatedResults,
    PrinterDownloadOut,
    PrinterSearchOccurrenceOut,
    RunSearchDataOut,
    SearchResultsExportCreate,
)
from database import UPLOADS_DIR, get_db
from logging_config import logger
from models.models import (
    AutomatedPrinterRecord,
    AutomatedResult,
    AutomatedRun,
    ListARecord,
    PrinterDownload,
    Project,
    Upload,
)
from services.automated_reconciliation import create_run, execute_run
from services.direct_isbn_search import direct_search_isbn, direct_search_isbns
from services.excel_parser import ColumnDetectionError
from services.normalized_export import export_normalized_for_run, normalized_export_filename
from services.normalizer import normalize_list_a
from services.search_results_export import build_search_results_excel

router = APIRouter(prefix="/reconciliation", tags=["automated-reconciliation"])


def _parse_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _run_out(run: AutomatedRun, db: Session) -> AutomatedRunOut:
    uploads = None
    if run.list_a_upload_id is not None:
        uploads = db.query(Upload).filter(Upload.id == run.list_a_upload_id).first()
    downloads = (
        db.query(PrinterDownload)
        .filter(PrinterDownload.run_id == run.id)
        .order_by(PrinterDownload.printer_slot)
        .all()
    )
    summary = json.loads(run.summary_json) if run.summary_json else None
    steps = json.loads(run.steps_json or "[]")
    return AutomatedRunOut(
        id=run.id,
        list_a_upload_id=run.list_a_upload_id,
        list_a_filename=uploads.filename if uploads else None,
        list_a_record_count=uploads.record_count if uploads else 0,
        list_a_isbn_count=uploads.isbn_detected_count if uploads else 0,
        printer_slots=_parse_json_list(run.printer_slots_json),
        start_date=run.start_date,
        end_date=run.end_date,
        status=run.status,
        steps=steps,
        summary=summary,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        downloads=[
            PrinterDownloadOut(
                id=d.id,
                printer_slot=d.printer_slot,
                printer_name=d.printer_name,
                start_date=d.start_date,
                end_date=d.end_date,
                filename=d.filename,
                retrieved_at=d.retrieved_at,
                record_count=d.record_count,
                file_size=d.file_size,
                status=d.status,
                error_message=d.error_message,
            )
            for d in downloads
        ],
    )


def _ensure_default_project(db: Session) -> Project:
    project = db.query(Project).order_by(Project.id.desc()).first()
    if project:
        return project
    from models.models import Printer

    project = Project(name="Printing Reconciliation")
    db.add(project)
    db.flush()
    for slot in (1, 2, 3):
        db.add(Printer(project_id=project.id, slot=slot, name=f"Printer {slot}"))
    db.commit()
    db.refresh(project)
    return project


@router.get("/list-a", response_model=list[dict])
def list_list_a_uploads(db: Session = Depends(get_db)):
    rows = (
        db.query(Upload)
        .filter(Upload.upload_type == "list_a")
        .order_by(Upload.id.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": u.id,
            "filename": u.filename,
            "record_count": u.record_count,
            "isbn_detected_count": u.isbn_detected_count,
            "isbn_column": u.isbn_column,
            "uploaded_at": u.uploaded_at,
            "project_id": u.project_id,
        }
        for u in rows
    ]


@router.post("/list-a/upload", response_model=dict)
async def upload_list_a_for_automation(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = _ensure_default_project(db)
    suffix = Path(file.filename or "list.xlsx").suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(status_code=400, detail="Please upload a valid List A file.")

    dest_dir = UPLOADS_DIR / str(project.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        normalized = normalize_list_a(str(dest))
    except ColumnDetectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("List A upload for automation failed")
        raise HTTPException(status_code=400, detail="Please upload a valid List A file.") from exc

    upload = Upload(
        project_id=project.id,
        upload_type="list_a",
        printer_id=None,
        filename=file.filename or dest.name,
        stored_path=str(dest),
        record_count=normalized["record_count"],
        isbn_detected_count=normalized["isbn_detected_count"],
        isbn_column=normalized["isbn_column"],
    )
    db.add(upload)
    db.flush()
    for rec in normalized["records"]:
        db.add(ListARecord(upload_id=upload.id, **rec))
    db.commit()
    db.refresh(upload)
    return {
        "id": upload.id,
        "filename": upload.filename,
        "record_count": upload.record_count,
        "isbn_detected_count": upload.isbn_detected_count,
        "isbn_column": upload.isbn_column,
        "uploaded_at": upload.uploaded_at,
        "project_id": upload.project_id,
    }


@router.post("/run", response_model=AutomatedRunOut)
def start_reconciliation_run(
    payload: AutomatedRunCreate,
    db: Session = Depends(get_db),
):
    try:
        run = create_run(
            db,
            list_a_upload_id=payload.list_a_id,
            printer_slots=payload.printer_ids,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Prefer thread so long printer I/O does not block the worker process event loop
    thread = threading.Thread(target=execute_run, args=(run.id,), daemon=True)
    thread.start()
    logger.info(
        "Started automated run id=%s printers=%s %s→%s",
        run.id,
        payload.printer_ids,
        payload.start_date,
        payload.end_date,
    )
    return _run_out(run, db)


@router.get("/run/{run_id}", response_model=AutomatedRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AutomatedRun).filter(AutomatedRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _run_out(run, db)


@router.get("/runs", response_model=list[AutomatedRunOut])
def list_runs(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.query(AutomatedRun).order_by(AutomatedRun.id.desc()).limit(limit).all()
    return [_run_out(r, db) for r in rows]


@router.get("/run/{run_id}/results", response_model=PaginatedAutomatedResults)
def get_run_results(
    run_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: str | None = None,
    isbn: str | None = None,
    printer: str | None = None,
    db: Session = Depends(get_db),
):
    run = db.query(AutomatedRun).filter(AutomatedRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    q = db.query(AutomatedResult).filter(AutomatedResult.run_id == run_id)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(AutomatedResult.status.in_(statuses))
    else:
        from services.reconciliation import (
            DUPLICATE_IN_LIST_A,
            FOUND,
            NEEDS_REVIEW,
            NOT_FOUND,
        )

        q = q.filter(
            AutomatedResult.status.in_([FOUND, NOT_FOUND, DUPLICATE_IN_LIST_A, NEEDS_REVIEW])
        )
    if isbn:
        digits = "".join(ch for ch in isbn if ch.isdigit())
        q = q.filter(AutomatedResult.isbn.ilike(f"%{digits or isbn}%"))
    if printer:
        q = q.filter(AutomatedResult.source.ilike(f"%{printer}%"))

    total = q.count()
    rows = (
        q.order_by(AutomatedResult.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        AutomatedResultOut(
            id=r.id,
            isbn=r.isbn,
            status=r.status,
            item=r.item,
            party=r.party,
            voucher_no=r.voucher_no,
            list_a_date=r.list_a_date,
            pending_qty=r.pending_qty,
            printer_names=_parse_json_list(r.printer_names),
            printer_dates=_parse_json_list(r.printer_dates),
            original_printer_values=_parse_json_list(r.original_printer_values),
            source=r.source,
            printer_occurrences=len(_parse_json_list(r.printer_record_ids)),
        )
        for r in rows
    ]
    return PaginatedAutomatedResults(total=total, page=page, page_size=page_size, items=items)


@router.get("/run/{run_id}/printer-records", response_model=PaginatedAutomatedResults)
def get_printer_records_view(
    run_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Audit view of raw printer rows — mapped into result-like objects for the table."""
    run = db.query(AutomatedRun).filter(AutomatedRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    q = db.query(AutomatedPrinterRecord).filter(AutomatedPrinterRecord.run_id == run_id)
    total = q.count()
    rows = (
        q.order_by(AutomatedPrinterRecord.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        AutomatedResultOut(
            id=r.id,
            isbn=r.isbn_normalized,
            status=r.status or ("OK" if r.is_valid_isbn else "ISBN_NOT_FOUND"),
            item=None,
            party=None,
            voucher_no=None,
            list_a_date=None,
            pending_qty=None,
            printer_names=[r.printer_name],
            printer_dates=[r.printer_date or ""],
            original_printer_values=[r.source_filename or ""],
            source=f"row {r.source_row}",
        )
        for r in rows
    ]
    return PaginatedAutomatedResults(total=total, page=page, page_size=page_size, items=items)


@router.get("/run/{run_id}/search-data", response_model=RunSearchDataOut)
def get_run_search_data(run_id: int, db: Session = Depends(get_db)):
    """Return List A ISBNs + all printer occurrences for in-app ISBN search.

    Printer occurrences are built from the SAME classify_run_downloads() path used by
    normalized Excel export (Sheet 2). Falls back to AutomatedPrinterRecord rows only
    when stored TSV is unavailable. Does not re-fetch printers or invent a second
    extraction/normalization algorithm.
    """
    run = db.query(AutomatedRun).filter(AutomatedRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status not in ("COMPLETED", "PARTIAL_SUCCESS"):
        raise HTTPException(
            status_code=409,
            detail="Search data is available only after a run completes.",
        )

    list_a_rows = []
    if run.list_a_upload_id is not None:
        list_a_rows = (
            db.query(ListARecord.isbn_normalized)
            .filter(
                ListARecord.upload_id == run.list_a_upload_id,
                ListARecord.isbn_normalized.isnot(None),
                ListARecord.isbn_normalized != "",
            )
            .all()
        )
    list_a_isbns = sorted({str(r[0]) for r in list_a_rows if r[0]})

    printer_occurrences: list[PrinterSearchOccurrenceOut] = []

    from services.normalized_export import classify_run_downloads

    classified = classify_run_downloads(db, run_id)
    if classified is not None:
        # Same traces as Excel Printer ISBNs sheet — preserve every occurrence.
        for t in classified.extracted:
            isbn = str(t.normalized_identifier or "").strip()
            if not isbn:
                continue
            printer_occurrences.append(
                PrinterSearchOccurrenceOut(
                    isbn=isbn,
                    print_date=t.print_date,
                    printer_name=t.printer_name or (
                        f"Printer {t.printer_slot}" if t.printer_slot else "Printer"
                    ),
                    printer_slot=int(t.printer_slot or 0),
                    source_filename=t.document_filename or t.raw_4010_value,
                    source_row=t.source_row,
                    job_id=t.job_id,
                    job_end=t.job_end,
                    print_start=t.print_start,
                    job_accept=t.job_accept,
                    result=t.result,
                    set_number=t.set_number,
                    output_set=t.output_set,
                )
            )
        logger.info(
            "Search-data run=%s source=TSV occurrences=%s list_a=%s",
            run_id,
            len(printer_occurrences),
            len(list_a_isbns),
        )
    else:
        # Fallback: DB rows written during the same run ingest (same extract_isbn).
        printer_rows = (
            db.query(AutomatedPrinterRecord)
            .filter(
                AutomatedPrinterRecord.run_id == run_id,
                AutomatedPrinterRecord.isbn_normalized.isnot(None),
                AutomatedPrinterRecord.isbn_normalized != "",
            )
            .order_by(AutomatedPrinterRecord.id)
            .all()
        )
        for r in printer_rows:
            job_fields = {}
            job_id = None
            if r.raw_json:
                try:
                    raw = json.loads(r.raw_json)
                except (json.JSONDecodeError, TypeError):
                    raw = {}
                from printers.joblog_adapter import compose_job_fields_from_raw

                job_fields = compose_job_fields_from_raw(raw if isinstance(raw, dict) else {})
                job_id = raw.get("_job_id") or raw.get("1122")
                job_id = str(job_id) if job_id not in (None, "") else None
            printer_occurrences.append(
                PrinterSearchOccurrenceOut(
                    isbn=str(r.isbn_normalized),
                    print_date=r.printer_date,
                    printer_name=r.printer_name,
                    printer_slot=r.printer_slot,
                    source_filename=r.source_filename,
                    source_row=r.source_row,
                    job_id=job_id,
                    job_end=job_fields.get("job_end"),
                    print_start=job_fields.get("print_start"),
                    job_accept=job_fields.get("job_accept"),
                    result=job_fields.get("result"),
                    set_number=job_fields.get("set_number"),
                    output_set=job_fields.get("output_set"),
                )
            )
        logger.warning(
            "Search-data run=%s source=DB_FALLBACK occurrences=%s (TSV unavailable)",
            run_id,
            len(printer_occurrences),
        )

    return RunSearchDataOut(
        run_id=run.id,
        start_date=run.start_date,
        end_date=run.end_date,
        list_a_isbns=list_a_isbns,
        printer_occurrences=printer_occurrences,
    )


@router.post("/search-isbn", response_model=DirectIsbnSearchOut)
def search_isbn_direct(payload: DirectIsbnSearchCreate, db: Session = Depends(get_db)):
    """Fetch printer records for the selected date range and search one ISBN.

    Reuses the same JobLog download/parse + extract_isbn path as automated runs.
    Does not create an AutomatedRun, reconciliation rows, or Excel export.
    """
    try:
        result = direct_search_isbn(
            db,
            isbn=payload.isbn,
            printer_slots=payload.printer_ids,
            start_date=payload.start_date,
            end_date=payload.end_date,
            list_a_upload_id=payload.list_a_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DirectIsbnSearchOut(
        query=result.query,
        normalized_isbn=result.normalized_isbn,
        start_date=result.start_date,
        end_date=result.end_date,
        list_a=result.list_a,
        printer=result.printer,
        status=result.status,
        occurrences=[
            PrinterSearchOccurrenceOut(
                isbn=o.isbn,
                print_date=o.print_date,
                printer_name=o.printer_name,
                printer_slot=o.printer_slot,
                source_filename=o.source_filename,
                source_row=o.source_row,
                job_id=o.job_id,
                job_end=o.job_end,
                print_start=o.print_start,
                job_accept=o.job_accept,
                result=o.result,
                set_number=o.set_number,
                output_set=o.output_set,
            )
            for o in result.occurrences
        ],
        printers=[
            DirectSearchPrinterStatusOut(
                slot=p.slot,
                name=p.name,
                ok=p.ok,
                record_count=p.record_count,
                match_count=p.match_count,
                error=p.error,
            )
            for p in result.printers
        ],
        steps=result.steps,
    )


def _occurrence_out(o) -> PrinterSearchOccurrenceOut:
    return PrinterSearchOccurrenceOut(
        isbn=o.isbn,
        print_date=o.print_date,
        printer_name=o.printer_name,
        printer_slot=o.printer_slot,
        source_filename=o.source_filename,
        source_row=o.source_row,
        job_id=o.job_id,
        job_end=o.job_end,
        print_start=o.print_start,
        job_accept=o.job_accept,
        result=o.result,
        set_number=o.set_number,
        output_set=o.output_set,
    )


@router.post("/search-isbns", response_model=DirectMultiIsbnSearchOut)
def search_isbns_direct(payload: DirectMultiIsbnSearchCreate, db: Session = Depends(get_db)):
    """Fetch printer records once per printer, then search many ISBNs.

    Same JobLog download/parse + extract_isbn path as single search / automated runs.
    Does not create an AutomatedRun, reconciliation rows, or Excel export.
    """
    try:
        result = direct_search_isbns(
            db,
            isbns=payload.isbns,
            printer_slots=payload.printer_ids,
            start_date=payload.start_date,
            end_date=payload.end_date,
            list_a_upload_id=payload.list_a_id,
            entered_count=payload.entered_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DirectMultiIsbnSearchOut(
        start_date=result.start_date,
        end_date=result.end_date,
        entered_count=result.entered_count,
        unique_count=result.unique_count,
        found_count=result.found_count,
        not_found_count=result.not_found_count,
        connection_issue_count=result.connection_issue_count,
        results=[
            DirectBatchItemOut(
                query=item.query,
                normalized_isbn=item.normalized_isbn,
                list_a=item.list_a,
                printer=item.printer,
                status=item.status,
                occurrences=[_occurrence_out(o) for o in item.occurrences],
            )
            for item in result.results
        ],
        printers=[
            DirectSearchPrinterStatusOut(
                slot=p.slot,
                name=p.name,
                ok=p.ok,
                record_count=p.record_count,
                match_count=p.match_count,
                error=p.error,
            )
            for p in result.printers
        ],
        steps=result.steps,
    )


@router.post("/search-results/export")
def export_search_results(payload: SearchResultsExportCreate):
    """Export already-displayed ISBN Search Results to Excel.

    Does not fetch printers or re-run search. Print Date is taken from each
    supplied row (same field the Search Results UI uses: print_date).
    """
    rows = [r.model_dump() for r in payload.rows]
    data = build_search_results_excel(rows)
    filename = "ISBN_Search_Results.xlsx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/run/{run_id}/retry-failed", response_model=AutomatedRunOut)
def retry_failed_printers(run_id: int, db: Session = Depends(get_db)):
    """Create a new run for only the printers that failed in the previous run."""
    run = db.query(AutomatedRun).filter(AutomatedRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    failed = [
        d.printer_slot
        for d in db.query(PrinterDownload).filter(PrinterDownload.run_id == run_id).all()
        if d.status == "FAILED"
    ]
    if not failed:
        raise HTTPException(status_code=400, detail="No failed printers to retry.")
    try:
        new_run = create_run(
            db,
            list_a_upload_id=run.list_a_upload_id,
            printer_slots=failed,
            start_date=run.start_date,
            end_date=run.end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    threading.Thread(target=execute_run, args=(new_run.id,), daemon=True).start()
    return _run_out(new_run, db)


@router.get("/run/{run_id}/export")
def export_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AutomatedRun).filter(AutomatedRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status not in ("COMPLETED", "PARTIAL_SUCCESS"):
        raise HTTPException(status_code=400, detail="Run is not complete.")

    from services.reconciliation import (
        FOUND,
        NEEDS_REVIEW,
        NOT_FOUND,
        PRINTER_RECORDS_NOT_IN_LIST_A,
        DUPLICATE_IN_LIST_A,
    )

    results = db.query(AutomatedResult).filter(AutomatedResult.run_id == run_id).all()
    printer_recs = (
        db.query(AutomatedPrinterRecord).filter(AutomatedPrinterRecord.run_id == run_id).all()
    )
    summary = json.loads(run.summary_json) if run.summary_json else {}

    def rows_for(*statuses: str):
        selected = [r for r in results if r.status in statuses] if statuses else [
            r
            for r in results
            if r.status in (FOUND, NOT_FOUND, DUPLICATE_IN_LIST_A, NEEDS_REVIEW)
        ]
        return [
            {
                "Status": r.status,
                "ISBN": str(r.isbn) if r.isbn else "",
                "Item": r.item or "",
                "Party": r.party or "",
                "Voucher No.": r.voucher_no or "",
                "List A Date": r.list_a_date or "",
                "Pending Qty": r.pending_qty or "",
                "Printer": ", ".join(_parse_json_list(r.printer_names)) or "—",
                "Printer Date": ", ".join(d for d in _parse_json_list(r.printer_dates) if d)
                or "—",
                "Printer Occurrences": len(_parse_json_list(r.printer_record_ids)),
                "Original Filename(s)": " | ".join(
                    v for v in _parse_json_list(r.original_printer_values) if v
                ),
            }
            for r in selected
        ]

    printer_raw_rows = []
    for r in printer_recs:
        raw_4010 = r.source_filename or ""
        try:
            raw = json.loads(r.raw_json or "{}")
            raw_4010 = raw.get("_raw_4010_value") or raw_4010
        except json.JSONDecodeError:
            pass
        printer_raw_rows.append(
            {
                "Printer": r.printer_name,
                "Printer Date": r.printer_date or "",
                "Source Row": r.source_row,
                "Raw 4010 Value": raw_4010,
                "Original Filename": r.source_filename or "",
                "ISBN": str(r.isbn_normalized) if r.isbn_normalized else "",
                "Status": r.status or "",
            }
        )

    summary_rows = [
        {"Section": "List A", "Metric": "List A Records", "Value": summary.get("list_a_records", 0)},
        {"Section": "List A", "Metric": "Unique ISBNs", "Value": summary.get("unique_isbns", 0)},
        {"Section": "List A", "Metric": "Found", "Value": summary.get("found", summary.get("matched", 0))},
        {"Section": "List A", "Metric": "Not Found", "Value": summary.get("not_found", summary.get("not_reported", 0))},
        {"Section": "List A", "Metric": "Duplicate List A", "Value": summary.get("duplicates", 0)},
        {"Section": "List A", "Metric": "Needs Review", "Value": summary.get("needs_review", 0)},
        {"Section": "Printer Audit", "Metric": "Printer Records", "Value": summary.get("printer_records", 0)},
        {"Section": "Printer Audit", "Metric": "Printer ISBNs", "Value": summary.get("printer_isbns", summary.get("valid_isbns", 0))},
        {
            "Section": "Printer Audit",
            "Metric": "Printer Records Not in List A",
            "Value": summary.get("printer_not_in_list_a", summary.get("unexpected", 0)),
        },
        {
            "Section": "Printer Audit",
            "Metric": "Printer Records Without Extractable Identifier",
            "Value": summary.get("printer_without_isbn", 0),
        },
    ]
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(rows_for() or [{"Status": ""}]).to_excel(
            writer, sheet_name="List A Reconciliation", index=False
        )
        pd.DataFrame(rows_for(FOUND) or [{"Status": ""}]).to_excel(
            writer, sheet_name="Found", index=False
        )
        pd.DataFrame(rows_for(NOT_FOUND) or [{"Status": ""}]).to_excel(
            writer, sheet_name="Not Found", index=False
        )
        pd.DataFrame(rows_for(PRINTER_RECORDS_NOT_IN_LIST_A) or [{"Status": ""}]).to_excel(
            writer, sheet_name="Printer Audit", index=False
        )
        pd.DataFrame(rows_for(NEEDS_REVIEW) or [{"Status": ""}]).to_excel(
            writer, sheet_name="Needs Review", index=False
        )
        pd.DataFrame(printer_raw_rows or [{"Printer": ""}]).to_excel(
            writer, sheet_name="Printer Raw Records", index=False
        )

        workbook = writer.book
        text_format = workbook.add_format({"num_format": "@"})
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            ws.set_column("B:B", 18, text_format)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="automated_reconciliation_{run_id}.xlsx"'
        },
    )


@router.get("/run/{run_id}/export/normalized")
def export_run_normalized(run_id: int, db: Session = Depends(get_db)):
    """Operations-facing 3-sheet ISBN report for an automated run."""
    try:
        buffer = export_normalized_for_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Normalized export failed for run %s", run_id)
        raise HTTPException(status_code=500, detail="Normalized export failed.") from exc

    filename = normalized_export_filename()
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
