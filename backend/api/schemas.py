"""API schemas / Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PrinterNameUpdate(BaseModel):
    slot: int = Field(..., ge=1, le=3)
    name: str = Field(..., min_length=1, max_length=255)


class ProjectCreate(BaseModel):
    name: str = Field(default="Printing Reconciliation", min_length=1, max_length=255)
    printers: list[PrinterNameUpdate] = Field(
        default_factory=lambda: [
            PrinterNameUpdate(slot=1, name="Printer 1 (192.168.2.7)"),
            PrinterNameUpdate(slot=2, name="Printer 2 (192.168.2.218)"),
            PrinterNameUpdate(slot=3, name="Printer 3 (192.168.2.176)"),
        ]
    )


class PrinterOut(BaseModel):
    id: int
    slot: int
    name: str

    model_config = {"from_attributes": True}


class UploadOut(BaseModel):
    id: int
    upload_type: str
    printer_id: int | None
    filename: str
    record_count: int
    isbn_detected_count: int
    isbn_column: str | None = None
    source_column: str | None = None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    reconciled_at: datetime | None
    printers: list[PrinterOut]
    uploads: list[UploadOut] = []

    model_config = {"from_attributes": True}


class SummaryOut(BaseModel):
    list_a_records: int = 0
    unique_isbns: int = 0
    found: int = 0
    not_found: int = 0
    duplicates: int = 0
    needs_review: int = 0
    printer_records: int = 0
    printer_isbns: int = 0
    printer_not_in_list_a: int = 0
    printer_without_isbn: int = 0
    total_results: int = 0
    # Backward-compatible aliases
    matched: int = 0
    not_reported: int = 0
    unexpected: int = 0
    invalid: int = 0
    multiple_occurrences: int = 0
    isbn_not_found: int = 0


class PrinterSummaryOut(BaseModel):
    printer_id: int
    printer_name: str
    slot: int
    records_received: int
    isbns_extracted: int
    isbns_not_extracted: int
    matched_with_list_a: int
    unexpected: int = 0
    printer_not_in_list_a: int = 0


class ReconciliationRowOut(BaseModel):
    id: int
    isbn: str | None
    status: str
    item: str | None
    party: str | None
    voucher_no: str | None
    list_a_date: str | None
    pending_qty: str | None
    printer_names: list[str] = []
    printer_dates: list[str] = []
    original_printer_values: list[str] = []
    source: str | None
    list_a_record_ids: list[int] = []
    printer_record_ids: list[int] = []
    printer_occurrences: int = 0

class PaginatedResults(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ReconciliationRowOut]


class IsbnDetailOut(BaseModel):
    isbn: str
    status: str
    list_a: list[dict[str, Any]]
    printer_records: list[dict[str, Any]]


class MessageOut(BaseModel):
    message: str
    detail: Any = None


class HealthOut(BaseModel):
    status: str
    service: str


class NetworkPrinterConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    protocol: str | None = None
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    joblog_path: str | None = Field(default=None, min_length=1, max_length=255)
    is_enabled: bool | None = None

    def model_post_init(self, __context) -> None:
        if self.protocol is not None:
            proto = self.protocol.strip().lower()
            if proto not in ("http", "https"):
                raise ValueError("protocol must be http or https")
            object.__setattr__(self, "protocol", proto)


class NetworkPrinterConfigOut(BaseModel):
    id: int
    slot: int
    name: str
    protocol: str
    host: str
    port: int
    joblog_path: str
    base_url: str
    joblog_url: str
    display_endpoint: str
    username_env: str
    password_env: str
    # Credential presence flags only — never the secret values
    username_configured: bool
    password_configured: bool
    is_enabled: bool
    last_connection_ok: bool | None = None
    last_connection_category: str | None = None
    last_connection_message: str | None = None
    last_connection_http_status: int | None = None
    last_connection_latency_ms: int | None = None
    last_checked_at: datetime | None = None
    verify_ssl: bool

    model_config = {"from_attributes": True}


class ConnectionTestOut(BaseModel):
    slot: int
    name: str
    display_endpoint: str
    ok: bool
    category: str
    message: str
    http_status: int | None = None
    latency_ms: int | None = None
    checked_at: datetime
    # Explicitly never include credentials
    password_configured: bool


class AutomatedRunCreate(BaseModel):
    list_a_id: int
    printer_ids: list[int] = Field(..., min_length=1)
    start_date: str  # YYYY-MM-DD
    end_date: str


class PrinterDownloadOut(BaseModel):
    id: int
    printer_slot: int
    printer_name: str
    start_date: str
    end_date: str
    filename: str | None = None
    retrieved_at: datetime | None = None
    record_count: int
    file_size: int
    status: str
    error_message: str | None = None


class AutomatedRunSummary(BaseModel):
    list_a_records: int = 0
    unique_isbns: int = 0
    found: int = 0
    not_found: int = 0
    duplicates: int = 0
    needs_review: int = 0
    printer_records: int = 0
    printer_isbns: int = 0
    valid_isbns: int = 0
    printer_not_in_list_a: int = 0
    printer_without_isbn: int = 0
    printers_ok: int = 0
    printers_failed: int = 0
    printer_slots: list[int] = []
    # Backward-compatible aliases
    matched: int = 0
    not_reported: int = 0
    unexpected: int = 0
    multiple_occurrences: int = 0


class AutomatedRunOut(BaseModel):
    id: int
    list_a_upload_id: int
    list_a_filename: str | None = None
    list_a_record_count: int = 0
    list_a_isbn_count: int = 0
    printer_slots: list[int]
    start_date: str
    end_date: str
    status: str
    steps: list[dict[str, Any]] = []
    summary: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    downloads: list[PrinterDownloadOut] = []


class AutomatedResultOut(BaseModel):
    id: int
    isbn: str | None
    status: str
    item: str | None
    party: str | None
    voucher_no: str | None
    list_a_date: str | None
    pending_qty: str | None
    printer_names: list[str] = []
    printer_dates: list[str] = []
    original_printer_values: list[str] = []
    source: str | None = None
    printer_occurrences: int = 0


class PaginatedAutomatedResults(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AutomatedResultOut]

