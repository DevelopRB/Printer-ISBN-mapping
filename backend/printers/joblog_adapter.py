"""Job-log CGI adapter — protocol confirmed in docs/printer-joblog-api.md (Phase 2C).

Do not invent parameters. Date filters use rs/re as YYYYMMDD.
Download uses cmd=dl (TSV). List view returns HTML with embedded joblog[] JS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import httpx

from logging_config import logger
from printers.base import BasePrinterAdapter, ConnectionTestResult
from printers.connection import (
    CONNECTED,
    CREDENTIALS_MISSING,
    JobLogPrinterAdapter as ConnectionAdapter,
    build_printer_ssl_context,
    category_label,
)
from settings import Settings, get_printer_credentials, settings as app_settings

# Confirmed from printer UI onJobLog() JavaScript
DEFAULT_CLM = (
    "1122,4001,4009,4010,4005,1630,1034,1091,2003,"
    "1000,1001,1002,1003,1004,1005,"
    "1285,1286,1287,1288,1289,1290,"
    "1006,1007,1008,1009,1010,1011,"
    "1041,1045,1022,4005,1047,2025,2106,"
    "1271,1272,1273,1274,1275,1401,"
    "1610,1611,1612,1613,1614,1615,1616,"
    "1617,1618,1619,1620,1276,1277,1278,1279,1621"
)

COL_JOB_NO = "1122"
COL_MODE = "4001"
COL_USER = "4009"
COL_FILENAME = "4010"
# Reception accept date parts (HTML indices 9–11). Kept for diagnostics.
COL_ACCEPT_YEAR = "1000"
COL_ACCEPT_MONTH = "1001"
COL_ACCEPT_DAY = "1002"
# CSV popup "Date" column uses makeJobDate(D[21]…D[26]) → column IDs 1006–1011.
# Print Date for Operations must match that popup Date (not download/today/range).
COL_PRINT_YEAR = "1006"
COL_PRINT_MONTH = "1007"
COL_PRINT_DAY = "1008"


@dataclass
class JobLogRecord:
    source_filename: str | None
    printer_date: str | None
    job_no: str | None = None
    user_name: str | None = None
    mode: str | None = None
    raw_fields: dict[str, str] = field(default_factory=dict)


@dataclass
class JobLogFetchResult:
    ok: bool
    mode: str  # html_list | tsv_download
    content_type: str | None
    content_disposition: str | None
    byte_length: int
    record_count: int
    records: list[JobLogRecord]
    meta: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def format_yyyymmdd(value: date | datetime | str) -> str:
    """Encode a date as YYYYMMDD (confirmed working format for rs/re)."""
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 8:
        return digits
    raise ValueError(f"Date must be YYYYMMDD-compatible, got: {value!r}")


def compose_printer_date(yy: str, mm: str, dd: str) -> str | None:
    if not (yy and mm and dd):
        return None
    try:
        year = int(yy)
        if year < 100:
            year += 2000
        return f"{year:04d}-{int(mm):02d}-{int(dd):02d}"
    except ValueError:
        return f"{yy}-{mm}-{dd}"


class JobLogCgiAdapter(BasePrinterAdapter):
    """Adapter for /goform/joblog.cgi (shared by Printers 1–3)."""

    def __init__(
        self,
        *,
        slot: int,
        name: str,
        protocol: str,
        host: str,
        port: int,
        joblog_path: str = "/goform/joblog.cgi",
        app_settings_override: Settings | None = None,
    ):
        self.slot = slot
        self.name = name
        self.protocol = protocol.lower().rstrip(":/")
        self.host = host.strip()
        self.port = int(port)
        self.joblog_path = joblog_path if joblog_path.startswith("/") else f"/{joblog_path}"
        self._settings = app_settings_override or app_settings
        self._client: httpx.Client | None = None
        self._conn = ConnectionAdapter(
            slot=slot,
            name=name,
            protocol=protocol,
            host=host,
            port=port,
            joblog_path=joblog_path,
            app_settings_override=self._settings,
        )

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    def connect(self) -> ConnectionTestResult:
        return self._conn.connect()

    def authenticate(self) -> ConnectionTestResult:
        """Ensure credentials exist and Digest auth can access joblog."""
        creds = get_printer_credentials(self.slot)
        if not creds.has_password_configured():
            return ConnectionTestResult(
                ok=False,
                category=CREDENTIALS_MISSING,
                message=f"{category_label(CREDENTIALS_MISSING)} ({creds.password_env})",
            )
        try:
            client = self._ensure_client()
            response = client.get(self.joblog_path)
            if response.status_code in (401, 403):
                from printers.connection import AUTHENTICATION_FAILED

                return ConnectionTestResult(
                    ok=False,
                    category=AUTHENTICATION_FAILED,
                    message=category_label(AUTHENTICATION_FAILED),
                    http_status=response.status_code,
                )
            return ConnectionTestResult(
                ok=True,
                category=CONNECTED,
                message=category_label(CONNECTED),
                http_status=response.status_code,
            )
        except Exception as exc:
            logger.info(
                "Joblog auth probe failed slot=%s error_type=%s",
                self.slot,
                type(exc).__name__,
            )
            return self._conn._map_httpx_error(exc, 0)  # noqa: SLF001

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._conn.disconnect()

    def _ensure_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        creds = get_printer_credentials(self.slot)
        password = creds.password()
        if password is None:
            raise RuntimeError(f"Missing password env {creds.password_env}")
        username = creds.username() or "admin"
        verify: Any = True
        if self.protocol == "https":
            verify = build_printer_ssl_context(verify=self._settings.printer_verify_ssl)
        timeout = httpx.Timeout(
            connect=self._settings.printer_connect_timeout_seconds,
            read=max(60.0, self._settings.printer_read_timeout_seconds),
            write=self._settings.printer_connect_timeout_seconds,
            pool=self._settings.printer_connect_timeout_seconds,
        )
        # Prefer Digest (what the printer advertises).
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify,
            follow_redirects=True,
            auth=httpx.DigestAuth(username, password),
        )
        return self._client

    def _form_data(
        self,
        *,
        cmd: str = "",
        start: str = "",
        end: str = "",
        rs: str = "",
        re_: str = "",
        viw: str = "",
        clm: str = DEFAULT_CLM,
    ) -> dict[str, str]:
        return {
            "cmd": cmd,
            "clm": clm,
            "viw": viw,
            "start": start,
            "end": end,
            "rs": rs,
            "re": re_,
            "clmmode": "0",
        }

    def get_job_log(self) -> JobLogFetchResult:
        """Fetch default joblog HTML list (current printer default window)."""
        client = self._ensure_client()
        response = client.get(self.joblog_path)
        return self.parse_response(response, preferred_mode="html_list")

    def fetch_job_log(self, start_date: date, end_date: date) -> JobLogFetchResult:
        """Fetch HTML list filtered by date (rs/re=YYYYMMDD)."""
        rs = format_yyyymmdd(start_date)
        re_ = format_yyyymmdd(end_date)
        client = self._ensure_client()
        response = client.post(
            self.joblog_path,
            data=self._form_data(rs=rs, re_=re_),
        )
        result = self.parse_response(response, preferred_mode="html_list")
        result.meta["rs"] = rs
        result.meta["re"] = re_
        return result

    def fetch_export(self, start_date: date, end_date: date) -> JobLogFetchResult:
        """Preferred automation path: cmd=dl TSV download for date range."""
        rs = format_yyyymmdd(start_date)
        re_ = format_yyyymmdd(end_date)
        client = self._ensure_client()
        response = client.post(
            self.joblog_path,
            data=self._form_data(cmd="dl", rs=rs, re_=re_),
        )
        result = self.parse_response(response, preferred_mode="tsv_download")
        result.meta["rs"] = rs
        result.meta["re"] = re_
        result.meta["cmd"] = "dl"
        return result

    def download_job_log(self, start_date: date, end_date: date) -> JobLogFetchResult:
        return self.fetch_export(start_date, end_date)

    def probe_debug(self) -> dict[str, Any]:
        """Sanitized diagnostics for the debug API (no secrets)."""
        info: dict[str, Any] = {
            "slot": self.slot,
            "name": self.name,
            "base_url": self.base_url,
            "joblog_path": self.joblog_path,
            "auth_scheme": "digest",
            "password_configured": get_printer_credentials(self.slot).has_password_configured(),
        }
        try:
            connect_result = self.connect()
            info["connect"] = {
                "ok": connect_result.ok,
                "category": connect_result.category,
                "message": connect_result.message,
                "http_status": connect_result.http_status,
            }
            if not connect_result.ok:
                return info

            auth_result = self.authenticate()
            info["authenticate"] = {
                "ok": auth_result.ok,
                "category": auth_result.category,
                "message": auth_result.message,
                "http_status": auth_result.http_status,
            }
            if not auth_result.ok:
                return info

            listing = self.get_job_log()
            info["default_list"] = {
                "ok": listing.ok,
                "mode": listing.mode,
                "content_type": listing.content_type,
                "byte_length": listing.byte_length,
                "record_count": listing.record_count,
                "meta": listing.meta,
                "sample_filenames": [r.source_filename for r in listing.records[:5] if r.source_filename],
                "sample_dates": [r.printer_date for r in listing.records[:5] if r.printer_date],
            }

            # Small confirmed date-window probe (does not invent params)
            today = date.today()
            week_ago = date.fromordinal(max(today.toordinal() - 7, date(2000, 1, 1).toordinal()))
            export = self.fetch_export(week_ago, today)
            info["export_last_7_days"] = {
                "ok": export.ok,
                "mode": export.mode,
                "content_type": export.content_type,
                "content_disposition": export.content_disposition,
                "byte_length": export.byte_length,
                "record_count": export.record_count,
                "rs": export.meta.get("rs"),
                "re": export.meta.get("re"),
                "sample_filenames": [r.source_filename for r in export.records[:5] if r.source_filename],
                "sample_dates": [r.printer_date for r in export.records[:5] if r.printer_date],
                "error": export.error,
            }
        finally:
            self.disconnect()
        return info

    def parse_response(
        self,
        response: httpx.Response,
        *,
        preferred_mode: str | None = None,
    ) -> JobLogFetchResult:
        ctype = (response.headers.get("content-type") or "").lower()
        disposition = response.headers.get("content-disposition")
        body = response.content

        if response.status_code >= 400:
            return JobLogFetchResult(
                ok=False,
                mode="error",
                content_type=ctype,
                content_disposition=disposition,
                byte_length=len(body),
                record_count=0,
                records=[],
                error=f"HTTP {response.status_code}",
            )

        if "octet-stream" in ctype or (disposition and "attachment" in disposition.lower()):
            records, meta = self._parse_tsv(body)
            return JobLogFetchResult(
                ok=True,
                mode="tsv_download",
                content_type=ctype,
                content_disposition=disposition,
                byte_length=len(body),
                record_count=len(records),
                records=records,
                meta=meta,
            )

        records, meta = self._parse_html_joblog_js(body.decode("utf-8", errors="replace"))
        return JobLogFetchResult(
            ok=True,
            mode=preferred_mode or "html_list",
            content_type=ctype,
            content_disposition=disposition,
            byte_length=len(body),
            record_count=len(records),
            records=records,
            meta=meta,
        )

    def _parse_tsv(self, body: bytes) -> tuple[list[JobLogRecord], dict[str, Any]]:
        text = body.decode("utf-8", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            return [], {"header": []}
        header = lines[0].split("\t")
        index = {name: i for i, name in enumerate(header)}
        records: list[JobLogRecord] = []
        for line in lines[1:]:
            parts = line.split("\t")

            def col(cid: str) -> str | None:
                i = index.get(cid)
                if i is None or i >= len(parts):
                    return None
                return parts[i]

            filename = col(COL_FILENAME)
            printer_date = compose_printer_date(
                col(COL_PRINT_YEAR) or "",
                col(COL_PRINT_MONTH) or "",
                col(COL_PRINT_DAY) or "",
            )
            # Fallback to accept date if end/print date parts missing
            if not printer_date:
                printer_date = compose_printer_date(
                    col(COL_ACCEPT_YEAR) or "",
                    col(COL_ACCEPT_MONTH) or "",
                    col(COL_ACCEPT_DAY) or "",
                )
            raw = {cid: (col(cid) or "") for cid in index}
            records.append(
                JobLogRecord(
                    source_filename=filename,
                    printer_date=printer_date,
                    job_no=col(COL_JOB_NO),
                    user_name=col(COL_USER),
                    mode=col(COL_MODE),
                    raw_fields=raw,
                )
            )
        return records, {"header": header, "row_count": len(records)}

    def _parse_html_joblog_js(self, html: str) -> tuple[list[JobLogRecord], dict[str, Any]]:
        # Header comment line in JS lists column IDs in order for joblog[] rows
        header_match = re.search(
            r"//\s*0\s+((?:\d+\s*)+)",
            html,
        )
        header_ids: list[str] = []
        if header_match:
            header_ids = re.findall(r"\d+", header_match.group(1))

        # Fallback to known order from DEFAULT_CLM if comment missing
        if not header_ids:
            header_ids = [p for p in DEFAULT_CLM.split(",") if p]

        index = {cid: i for i, cid in enumerate(header_ids)}
        records: list[JobLogRecord] = []
        for m in re.finditer(r'joblog\[(\d+)\]\s*=\s*"([^"]*)"', html):
            parts = m.group(2).split("\t")

            def col(cid: str) -> str | None:
                i = index.get(cid)
                if i is None or i >= len(parts):
                    return None
                return parts[i]

            records.append(
                JobLogRecord(
                    source_filename=col(COL_FILENAME),
                    printer_date=compose_printer_date(
                        col(COL_PRINT_YEAR) or "",
                        col(COL_PRINT_MONTH) or "",
                        col(COL_PRINT_DAY) or "",
                    )
                    or compose_printer_date(
                        col(COL_ACCEPT_YEAR) or "",
                        col(COL_ACCEPT_MONTH) or "",
                        col(COL_ACCEPT_DAY) or "",
                    ),
                    job_no=col(COL_JOB_NO),
                    user_name=col(COL_USER),
                    mode=col(COL_MODE),
                    raw_fields={cid: (col(cid) or "") for cid in index},
                )
            )

        meta = {
            "header_ids": header_ids,
            "logstart": _js_int(html, "logstart"),
            "logend": _js_int(html, "logend"),
            "logtotal": _js_int(html, "logtotal"),
        }
        return records, meta


def _js_int(html: str, name: str) -> int | None:
    m = re.search(rf"\b{name}\s*=\s*(\d+)", html)
    return int(m.group(1)) if m else None


def build_joblog_adapter_from_config(config) -> JobLogCgiAdapter:
    return JobLogCgiAdapter(
        slot=config.slot,
        name=config.name,
        protocol=config.protocol,
        host=config.host,
        port=config.port,
        joblog_path=config.joblog_path,
    )


# Back-compat alias expected by package docs
JobLogAdapter = JobLogCgiAdapter
