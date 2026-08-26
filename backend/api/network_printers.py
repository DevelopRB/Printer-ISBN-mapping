"""Network printer configuration and connection-test API (Phase 2A/2B).

Never returns passwords or credential values.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas import ConnectionTestOut, NetworkPrinterConfigOut, NetworkPrinterConfigUpdate
from database import get_db
from logging_config import logger
from models.models import NetworkPrinterConfig
from printers.connection import build_adapter_from_config
from services.printer_config_service import ensure_network_printer_configs
from settings import get_printer_credentials, settings

router = APIRouter(prefix="/network-printers", tags=["network-printers"])
printers_debug_router = APIRouter(prefix="/printers", tags=["printers-debug"])


def _to_out(row: NetworkPrinterConfig) -> NetworkPrinterConfigOut:
    creds = get_printer_credentials(row.slot)
    protocol = row.protocol.lower()
    base_url = f"{protocol}://{row.host}:{row.port}"
    path = row.joblog_path if row.joblog_path.startswith("/") else f"/{row.joblog_path}"
    return NetworkPrinterConfigOut(
        id=row.id,
        slot=row.slot,
        name=row.name,
        protocol=protocol,
        host=row.host,
        port=row.port,
        joblog_path=path,
        base_url=base_url,
        joblog_url=f"{base_url}{path}",
        display_endpoint=f"{row.host}:{row.port}",
        username_env=row.username_env,
        password_env=row.password_env,
        username_configured=creds.has_username_configured(),
        password_configured=creds.has_password_configured(),
        is_enabled=bool(row.is_enabled),
        last_connection_ok=None if row.last_connection_ok is None else bool(row.last_connection_ok),
        last_connection_category=row.last_connection_category,
        last_connection_message=row.last_connection_message,
        last_connection_http_status=row.last_connection_http_status,
        last_connection_latency_ms=row.last_connection_latency_ms,
        last_checked_at=row.last_checked_at,
        verify_ssl=settings.printer_verify_ssl if protocol == "https" else True,
    )


@router.get("", response_model=list[NetworkPrinterConfigOut])
def list_network_printers(db: Session = Depends(get_db)):
    rows = ensure_network_printer_configs(db)
    return [_to_out(r) for r in rows]


@router.get("/{slot}", response_model=NetworkPrinterConfigOut)
def get_network_printer(slot: int, db: Session = Depends(get_db)):
    if slot not in (1, 2, 3):
        raise HTTPException(status_code=404, detail="Printer slot not found.")
    ensure_network_printer_configs(db)
    row = db.query(NetworkPrinterConfig).filter(NetworkPrinterConfig.slot == slot).first()
    if not row:
        raise HTTPException(status_code=404, detail="Printer configuration not found.")
    return _to_out(row)


@router.patch("/{slot}", response_model=NetworkPrinterConfigOut)
def update_network_printer(
    slot: int,
    payload: NetworkPrinterConfigUpdate,
    db: Session = Depends(get_db),
):
    if slot not in (1, 2, 3):
        raise HTTPException(status_code=404, detail="Printer slot not found.")
    ensure_network_printer_configs(db)
    row = db.query(NetworkPrinterConfig).filter(NetworkPrinterConfig.slot == slot).first()
    if not row:
        raise HTTPException(status_code=404, detail="Printer configuration not found.")

    data = payload.model_dump(exclude_unset=True)
    if "protocol" in data and data["protocol"] is not None:
        data["protocol"] = data["protocol"].lower()
    if "is_enabled" in data and data["is_enabled"] is not None:
        data["is_enabled"] = 1 if data["is_enabled"] else 0
    if "joblog_path" in data and data["joblog_path"]:
        path = data["joblog_path"].strip()
        data["joblog_path"] = path if path.startswith("/") else f"/{path}"

    for key, value in data.items():
        if value is not None:
            setattr(row, key, value)

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    logger.info("Updated network printer config slot=%s host=%s:%s", row.slot, row.host, row.port)
    return _to_out(row)


@router.post("/{slot}/test-connection", response_model=ConnectionTestOut)
def test_network_printer_connection(slot: int, db: Session = Depends(get_db)):
    if slot not in (1, 2, 3):
        raise HTTPException(status_code=404, detail="Printer slot not found.")
    ensure_network_printer_configs(db)
    row = db.query(NetworkPrinterConfig).filter(NetworkPrinterConfig.slot == slot).first()
    if not row:
        raise HTTPException(status_code=404, detail="Printer configuration not found.")

    creds = get_printer_credentials(slot)
    adapter = build_adapter_from_config(row)
    logger.info(
        "Testing printer connection slot=%s endpoint=%s:%s verify_ssl=%s",
        slot,
        row.host,
        row.port,
        settings.printer_verify_ssl if row.protocol.lower() == "https" else "n/a",
    )

    try:
        result = adapter.test_connection(include_auth=True)
    except Exception:
        logger.exception("Unexpected printer connection test error slot=%s", slot)
        raise HTTPException(
            status_code=500,
            detail="Connection test failed. Check application logs.",
        ) from None
    finally:
        adapter.disconnect()

    checked_at = datetime.now(timezone.utc)
    row.last_connection_ok = 1 if result.ok else 0
    row.last_connection_category = result.category
    row.last_connection_message = result.message
    row.last_connection_http_status = result.http_status
    row.last_connection_latency_ms = result.latency_ms
    row.last_checked_at = checked_at
    db.commit()

    return ConnectionTestOut(
        slot=row.slot,
        name=row.name,
        display_endpoint=f"{row.host}:{row.port}",
        ok=result.ok,
        category=result.category,
        message=result.message,
        http_status=result.http_status,
        latency_ms=result.latency_ms,
        checked_at=checked_at,
        password_configured=creds.has_password_configured(),
    )


def _run_joblog_debug(target: int, db: Session) -> dict:
    if not settings.printer_joblog_debug:
        raise HTTPException(status_code=404, detail="Joblog debug endpoint is disabled.")
    if target not in (1, 2, 3):
        raise HTTPException(status_code=404, detail="Printer slot not found.")

    ensure_network_printer_configs(db)
    row = db.query(NetworkPrinterConfig).filter(NetworkPrinterConfig.slot == target).first()
    if not row:
        raise HTTPException(status_code=404, detail="Printer configuration not found.")

    from printers.joblog_adapter import build_joblog_adapter_from_config

    adapter = build_joblog_adapter_from_config(row)
    logger.info("Joblog debug probe slot=%s host=%s:%s", target, row.host, row.port)
    try:
        return adapter.probe_debug()
    except Exception:
        logger.exception("Joblog debug probe failed slot=%s", target)
        raise HTTPException(
            status_code=500,
            detail="Joblog debug probe failed. Check application logs.",
        ) from None
    finally:
        adapter.disconnect()


@router.get("/{slot}/joblog/debug")
def joblog_debug_network(slot: int, db: Session = Depends(get_db)):
    """Development-only sanitized joblog probe. Disabled when PRINTER_JOBLOG_DEBUG=false."""
    return _run_joblog_debug(slot, db)


@printers_debug_router.get("/{printer_id}/joblog/debug")
def joblog_debug_alias(printer_id: int, db: Session = Depends(get_db)):
    """Alias matching Phase 2C spec path: /api/printers/{printer_id}/joblog/debug."""
    return _run_joblog_debug(printer_id, db)
