"""Seed and helpers for network printer configuration rows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.models import NetworkPrinterConfig
from settings import DEFAULT_PRINTER_ENDPOINTS, PRINTER_CREDENTIAL_REFS


def ensure_network_printer_configs(db: Session) -> list[NetworkPrinterConfig]:
    """Create default network printer rows if missing. Does not overwrite edits."""
    existing = {
        row.slot: row
        for row in db.query(NetworkPrinterConfig).order_by(NetworkPrinterConfig.slot).all()
    }
    created = False
    for slot, defaults in DEFAULT_PRINTER_ENDPOINTS.items():
        if slot in existing:
            continue
        creds = PRINTER_CREDENTIAL_REFS[slot]
        row = NetworkPrinterConfig(
            slot=slot,
            name=defaults["name"],
            protocol=defaults["protocol"],
            host=defaults["host"],
            port=defaults["port"],
            joblog_path=defaults["joblog_path"],
            username_env=creds.username_env,
            password_env=creds.password_env,
            is_enabled=1,
        )
        db.add(row)
        created = True
    if created:
        db.commit()
    return db.query(NetworkPrinterConfig).order_by(NetworkPrinterConfig.slot).all()
