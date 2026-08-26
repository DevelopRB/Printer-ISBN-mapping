"""Project, upload, reconciliation, and export API routes."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from database import UPLOADS_DIR, get_db
from logging_config import logger
from models.models import (
    ListARecord,
    Printer,
    PrinterRecord,
    Project,
    ReconciliationResult,
    Upload,
)
from api.schemas import (
    HealthOut,
    IsbnDetailOut,
    MessageOut,
    PaginatedResults,
    PrinterNameUpdate,
    PrinterOut,
    PrinterSummaryOut,
    ProjectCreate,
    ProjectOut,
    ReconciliationRowOut,
    SummaryOut,
    UploadOut,
)
from services.excel_parser import ColumnDetectionError
from services.export_service import export_workbook
from services.normalized_export import export_normalized_for_project, normalized_export_filename
from services.normalizer import normalize_list_a, normalize_printer
from services.reconciliation import (
    compute_summary,
    get_printer_summaries,
    run_reconciliation,
)

router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def _parse_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _result_to_out(r: ReconciliationResult) -> ReconciliationRowOut:
    printer_ids = _parse_json_list(r.printer_record_ids)
    return ReconciliationRowOut(
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
        list_a_record_ids=_parse_json_list(r.list_a_record_ids),
        printer_record_ids=printer_ids,
        printer_occurrences=len(printer_ids),
    )


@router.get("/health", response_model=HealthOut)
def health():
    return HealthOut(status="ok", service="Printing Reconciliation System")


@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=payload.name)
    db.add(project)
    db.flush()

    names = {p.slot: p.name for p in payload.printers}
    for slot in (1, 2, 3):
        db.add(
            Printer(
                project_id=project.id,
                slot=slot,
                name=names.get(slot, f"Printer {slot}"),
            )
        )
    db.commit()
    db.refresh(project)
    project = (
        db.query(Project)
        .options(joinedload(Project.printers), joinedload(Project.uploads))
        .filter(Project.id == project.id)
        .first()
    )
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return (
        db.query(Project)
        .options(joinedload(Project.printers), joinedload(Project.uploads))
        .order_by(Project.id.desc())
        .all()
    )


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = (
        db.query(Project)
        .options(joinedload(Project.printers), joinedload(Project.uploads))
        .filter(Project.id == project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.patch("/projects/{project_id}/printers", response_model=list[PrinterOut])
def update_printer_names(
    project_id: int,
    printers: list[PrinterNameUpdate],
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    existing = {p.slot: p for p in db.query(Printer).filter(Printer.project_id == project_id).all()}
    for item in printers:
        if item.slot in existing:
            existing[item.slot].name = item.name.strip()
    db.commit()
    return (
        db.query(Printer)
        .filter(Printer.project_id == project_id)
        .order_by(Printer.slot)
        .all()
    )


def _save_upload(file: UploadFile, project_id: int) -> Path:
    suffix = Path(file.filename or "upload.xlsx").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Use .xlsx, .xls, or .csv.",
        )
    dest_dir = UPLOADS_DIR / str(project_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    return dest


@router.post("/projects/{project_id}/upload/list-a", response_model=UploadOut)
async def upload_list_a(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        stored = _save_upload(file, project_id)
        normalized = normalize_list_a(str(stored))
    except ColumnDetectionError as exc:
        logger.error("List A column detection failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        logger.error("List A parse failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected List A upload error")
        raise HTTPException(status_code=400, detail="Failed to process List A file.") from exc

    # Replace prior List A uploads for this project
    old_uploads = (
        db.query(Upload)
        .filter(Upload.project_id == project_id, Upload.upload_type == "list_a")
        .all()
    )
    for old in old_uploads:
        db.delete(old)
    db.flush()

    upload = Upload(
        project_id=project_id,
        upload_type="list_a",
        printer_id=None,
        filename=file.filename or stored.name,
        stored_path=str(stored),
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
    logger.info(
        "List A uploaded project=%s records=%s isbns=%s",
        project_id,
        upload.record_count,
        upload.isbn_detected_count,
    )
    return upload


@router.post("/projects/{project_id}/upload/printer", response_model=UploadOut)
async def upload_printer(
    project_id: int,
    printer_slot: int = Form(..., ge=1, le=3),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    printer = (
        db.query(Printer)
        .filter(Printer.project_id == project_id, Printer.slot == printer_slot)
        .first()
    )
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found.")

    try:
        stored = _save_upload(file, project_id)
        normalized = normalize_printer(str(stored))
    except ColumnDetectionError as exc:
        logger.error("Printer column detection failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        logger.error("Printer parse failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected printer upload error")
        raise HTTPException(status_code=400, detail="Failed to process printer file.") from exc

    old_uploads = (
        db.query(Upload)
        .filter(
            Upload.project_id == project_id,
            Upload.upload_type == "printer",
            Upload.printer_id == printer.id,
        )
        .all()
    )
    for old in old_uploads:
        db.delete(old)
    db.flush()

    upload = Upload(
        project_id=project_id,
        upload_type="printer",
        printer_id=printer.id,
        filename=file.filename or stored.name,
        stored_path=str(stored),
        record_count=normalized["record_count"],
        isbn_detected_count=normalized["isbn_detected_count"],
        source_column=normalized["source_column"],
    )
    db.add(upload)
    db.flush()

    for rec in normalized["records"]:
        db.add(PrinterRecord(upload_id=upload.id, printer_id=printer.id, **rec))

    db.commit()
    db.refresh(upload)
    logger.info(
        "Printer uploaded project=%s slot=%s records=%s isbns=%s",
        project_id,
        printer_slot,
        upload.record_count,
        upload.isbn_detected_count,
    )
    return upload


@router.post("/projects/{project_id}/reconcile", response_model=SummaryOut)
def reconcile(project_id: int, db: Session = Depends(get_db)):
    project = (
        db.query(Project)
        .options(joinedload(Project.uploads))
        .filter(Project.id == project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    list_a_uploads = [u for u in project.uploads if u.upload_type == "list_a"]
    printer_uploads = [u for u in project.uploads if u.upload_type == "printer"]

    if not list_a_uploads:
        raise HTTPException(status_code=400, detail="List A was not uploaded.")
    if not list_a_uploads[0].isbn_column:
        raise HTTPException(status_code=400, detail="Could not find an ISBN column in List A.")
    if not printer_uploads:
        raise HTTPException(status_code=400, detail="At least one printer file must be uploaded.")
    for u in printer_uploads:
        if not u.source_column:
            raise HTTPException(status_code=400, detail="Could not find printer field 4010.")

    try:
        summary = run_reconciliation(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Reconciliation failed for project %s", project_id)
        raise HTTPException(status_code=500, detail="Reconciliation failed. Check application logs.") from exc

    return summary


@router.get("/projects/{project_id}/summary", response_model=SummaryOut)
def get_summary(project_id: int, db: Session = Depends(get_db)):
    return compute_summary(db, project_id)


@router.get("/projects/{project_id}/printer-summaries", response_model=list[PrinterSummaryOut])
def printer_summaries(project_id: int, db: Session = Depends(get_db)):
    return get_printer_summaries(db, project_id)


@router.get("/projects/{project_id}/results", response_model=PaginatedResults)
def get_results(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: str | None = None,
    printer: str | None = None,
    party: str | None = None,
    isbn: str | None = None,
    item: str | None = None,
    voucher_no: str | None = None,
    date: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(ReconciliationResult).filter(ReconciliationResult.project_id == project_id)

    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(ReconciliationResult.status.in_(statuses))
    else:
        # Default: List A primary reconciliation (exclude printer audit rows)
        from services.reconciliation import (
            DUPLICATE_IN_LIST_A,
            FOUND,
            NEEDS_REVIEW,
            NOT_FOUND,
        )

        q = q.filter(
            ReconciliationResult.status.in_(
                [FOUND, NOT_FOUND, DUPLICATE_IN_LIST_A, NEEDS_REVIEW]
            )
        )
    if party:
        q = q.filter(ReconciliationResult.party.ilike(f"%{party}%"))
    if isbn:
        digits = "".join(ch for ch in isbn if ch.isdigit())
        if digits:
            q = q.filter(ReconciliationResult.isbn.ilike(f"%{digits}%"))
        else:
            q = q.filter(ReconciliationResult.isbn.ilike(f"%{isbn}%"))
    if item:
        q = q.filter(ReconciliationResult.item.ilike(f"%{item}%"))
    if voucher_no:
        q = q.filter(ReconciliationResult.voucher_no.ilike(f"%{voucher_no}%"))
    if date:
        q = q.filter(ReconciliationResult.list_a_date.ilike(f"%{date}%"))
    if printer:
        q = q.filter(ReconciliationResult.source.ilike(f"%{printer}%"))

    total = q.count()
    rows = (
        q.order_by(ReconciliationResult.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResults(
        total=total,
        page=page,
        page_size=page_size,
        items=[_result_to_out(r) for r in rows],
    )


@router.get("/projects/{project_id}/isbn/{isbn}", response_model=IsbnDetailOut)
def isbn_detail(project_id: int, isbn: str, db: Session = Depends(get_db)):
    clean = "".join(ch for ch in isbn if ch.isdigit())
    list_recs = (
        db.query(ListARecord)
        .join(ListARecord.upload)
        .filter(
            ListARecord.upload.has(project_id=project_id),
            ListARecord.isbn_normalized == clean,
        )
        .all()
    )
    printer_recs = (
        db.query(PrinterRecord)
        .options(joinedload(PrinterRecord.printer))
        .join(PrinterRecord.upload)
        .filter(
            PrinterRecord.upload.has(project_id=project_id),
            PrinterRecord.isbn_normalized == clean,
        )
        .all()
    )
    result = (
        db.query(ReconciliationResult)
        .filter(
            ReconciliationResult.project_id == project_id,
            ReconciliationResult.isbn == clean,
        )
        .first()
    )

    printers = (
        db.query(Printer)
        .filter(Printer.project_id == project_id)
        .order_by(Printer.slot)
        .all()
    )
    by_printer: dict[int, list] = {p.id: [] for p in printers}
    for pr in printer_recs:
        by_printer.setdefault(pr.printer_id, []).append(pr)

    printer_view = []
    for p in printers:
        hits = by_printer.get(p.id, [])
        if not hits:
            printer_view.append(
                {
                    "printer_id": p.id,
                    "printer_name": p.name,
                    "found": False,
                    "records": [],
                }
            )
        else:
            printer_view.append(
                {
                    "printer_id": p.id,
                    "printer_name": p.name,
                    "found": True,
                    "records": [
                        {
                            "date": h.printer_date,
                            "original_value": h.source_value,
                            "source_row_number": h.source_row_number,
                        }
                        for h in hits
                    ],
                }
            )

    return IsbnDetailOut(
        isbn=clean,
        status=result.status if result else "UNKNOWN",
        list_a=[
            {
                "id": r.id,
                "item": r.item,
                "party": r.party,
                "voucher_no": r.voucher_no,
                "date": r.date,
                "pending_qty": r.pending_qty,
                "unit": r.unit,
                "isbn_original": r.isbn_original,
            }
            for r in list_recs
        ],
        printer_records=printer_view,
    )


@router.get("/projects/{project_id}/export")
def export_excel(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if not project.reconciled_at:
        raise HTTPException(status_code=400, detail="Run reconciliation before exporting.")

    try:
        buffer = export_workbook(db, project_id)
    except Exception as exc:
        logger.exception("Export failed")
        raise HTTPException(status_code=500, detail="Export failed.") from exc

    filename = f"reconciliation_project_{project_id}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/export/normalized")
def export_normalized_excel(project_id: int, db: Session = Depends(get_db)):
    """Operations-facing 3-sheet ISBN report (List A / Printer / Reconciliation)."""
    try:
        buffer = export_normalized_for_project(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Normalized export failed")
        raise HTTPException(status_code=500, detail="Normalized export failed.") from exc

    filename = normalized_export_filename()
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
