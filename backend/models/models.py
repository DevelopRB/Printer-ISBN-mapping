"""SQLAlchemy models for the Printing Reconciliation System."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    printers = relationship("Printer", back_populates="project", cascade="all, delete-orphan")
    uploads = relationship("Upload", back_populates="project", cascade="all, delete-orphan")
    reconciliation_results = relationship(
        "ReconciliationResult", back_populates="project", cascade="all, delete-orphan"
    )


class Printer(Base):
    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, or 3
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    project = relationship("Project", back_populates="printers")
    uploads = relationship("Upload", back_populates="printer")
    printer_records = relationship("PrinterRecord", back_populates="printer")


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    upload_type: Mapped[str] = mapped_column(String(50), nullable=False)  # list_a | printer
    printer_id: Mapped[int | None] = mapped_column(ForeignKey("printers.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    isbn_detected_count: Mapped[int] = mapped_column(Integer, default=0)
    isbn_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="uploads")
    printer = relationship("Printer", back_populates="uploads")
    list_a_records = relationship("ListARecord", back_populates="upload", cascade="all, delete-orphan")
    printer_records = relationship(
        "PrinterRecord", back_populates="upload", cascade="all, delete-orphan"
    )


class ListARecord(Base):
    __tablename__ = "list_a_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    isbn_original: Mapped[str | None] = mapped_column(String(255), nullable=True)
    isbn_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_valid_isbn: Mapped[int] = mapped_column(Integer, default=0)  # 0/1
    date: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voucher_no: Mapped[str | None] = mapped_column(String(255), nullable=True)
    party: Mapped[str | None] = mapped_column(String(512), nullable=True)
    item: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pending_qty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_data_json: Mapped[str] = mapped_column(Text, nullable=False)

    upload = relationship("Upload", back_populates="list_a_records")


class PrinterRecord(Base):
    __tablename__ = "printer_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"), nullable=False)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id"), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    isbn_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_valid_isbn: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ISBN_NOT_FOUND etc.
    printer_date: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_data_json: Mapped[str] = mapped_column(Text, nullable=False)

    upload = relationship("Upload", back_populates="printer_records")
    printer = relationship("Printer", back_populates="printer_records")


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    printer_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    list_a_record_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    printer_record_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    item: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    party: Mapped[str | None] = mapped_column(String(512), nullable=True)
    voucher_no: Mapped[str | None] = mapped_column(String(255), nullable=True)
    list_a_date: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pending_qty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    printer_names: Mapped[str | None] = mapped_column(Text, nullable=True)
    printer_dates: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_printer_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="reconciliation_results")


class NetworkPrinterConfig(Base):
    """Global network printer endpoint configuration (non-secret).

    Passwords are NEVER stored here — only env var *names* for credentials.
    """

    __tablename__ = "network_printer_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)  # 1, 2, or 3
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol: Mapped[str] = mapped_column(String(10), nullable=False)  # http | https
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    joblog_path: Mapped[str] = mapped_column(String(255), nullable=False, default="/goform/joblog.cgi")
    username_env: Mapped[str] = mapped_column(String(100), nullable=False)
    password_env: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[int] = mapped_column(Integer, default=1)  # 0/1
    last_connection_ok: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0/1/None
    last_connection_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_connection_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_connection_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_connection_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AutomatedRun(Base):
    """History of automated fetch + reconciliation runs."""

    __tablename__ = "automated_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    list_a_upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("uploads.id"), nullable=True
    )
    printer_slots_json: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. [1,2]
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    # PENDING | RUNNING | COMPLETED | PARTIAL_SUCCESS | FAILED
    steps_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    downloads = relationship(
        "PrinterDownload", back_populates="run", cascade="all, delete-orphan"
    )
    printer_records = relationship(
        "AutomatedPrinterRecord", back_populates="run", cascade="all, delete-orphan"
    )
    results = relationship(
        "AutomatedResult", back_populates="run", cascade="all, delete-orphan"
    )


class PrinterDownload(Base):
    """Raw TSV retrieval audit record (never overwritten)."""

    __tablename__ = "printer_downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("automated_runs.id"), nullable=False)
    printer_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    printer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    # PENDING | COMPLETED | FAILED | EMPTY
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run = relationship("AutomatedRun", back_populates="downloads")


class AutomatedPrinterRecord(Base):
    __tablename__ = "automated_printer_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("automated_runs.id"), nullable=False)
    download_id: Mapped[int | None] = mapped_column(ForeignKey("printer_downloads.id"), nullable=True)
    printer_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    printer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    isbn_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_valid_isbn: Mapped[int] = mapped_column(Integer, default=0)
    printer_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    run = relationship("AutomatedRun", back_populates="printer_records")


class AutomatedResult(Base):
    __tablename__ = "automated_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("automated_runs.id"), nullable=False, index=True)
    isbn: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    party: Mapped[str | None] = mapped_column(String(512), nullable=True)
    voucher_no: Mapped[str | None] = mapped_column(String(255), nullable=True)
    list_a_date: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pending_qty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    printer_names: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    printer_dates: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_printer_values: Mapped[str | None] = mapped_column(Text, nullable=True)
    list_a_record_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    printer_record_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    run = relationship("AutomatedRun", back_populates="results")
