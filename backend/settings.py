"""Application settings loaded from environment variables.

Printer passwords MUST come from the environment (or a secrets manager).
They are never stored in the database, returned by APIs, or sent to the frontend.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from runtime_paths import env_file_candidates, is_packaged_runtime

# Load .env files: explicit Electron userData file first, then project/backend.
for candidate in env_file_candidates():
    if candidate.is_file():
        load_dotenv(candidate, override=True)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PrinterCredentialRef:
    """References to env vars for a printer — never holds the password value in logs."""

    slot: int
    username_env: str
    password_env: str

    def username(self) -> str | None:
        value = os.getenv(self.username_env)
        if value is None or not value.strip():
            return None
        return value.strip()

    def password(self) -> str | None:
        value = os.getenv(self.password_env)
        if value is None or value == "":
            return None
        return value

    def has_password_configured(self) -> bool:
        return self.password() is not None

    def has_username_configured(self) -> bool:
        return self.username() is not None


# Default network endpoints (non-secret). Overridable via DB after seed.
DEFAULT_PRINTER_ENDPOINTS = {
    1: {
        "name": "Printer 1",
        "protocol": "https",
        "host": "192.168.2.7",
        "port": 30092,
        "joblog_path": "/goform/joblog.cgi",
    },
    2: {
        "name": "Printer 2",
        "protocol": "https",
        "host": "192.168.2.218",
        "port": 30092,
        "joblog_path": "/goform/joblog.cgi",
    },
    3: {
        "name": "Printer 3",
        "protocol": "http",
        "host": "192.168.2.176",
        "port": 30091,
        "joblog_path": "/goform/joblog.cgi",
    },
}

PRINTER_CREDENTIAL_REFS = {
    1: PrinterCredentialRef(1, "PRINTER_1_USERNAME", "PRINTER_1_PASSWORD"),
    2: PrinterCredentialRef(2, "PRINTER_2_USERNAME", "PRINTER_2_PASSWORD"),
    3: PrinterCredentialRef(3, "PRINTER_3_USERNAME", "PRINTER_3_PASSWORD"),
}


class Settings:
    """Runtime settings. PRINTER_VERIFY_SSL applies ONLY to printer HTTP clients."""

    # When false, TLS certificate verification is skipped for configured printer hosts.
    # Security implication: MitM risk on the path to the printer. Acceptable only on
    # a trusted internal network with known printer IPs. Do not use on public networks.
    printer_verify_ssl: bool = _env_bool("PRINTER_VERIFY_SSL", default=False)
    printer_connect_timeout_seconds: float = float(os.getenv("PRINTER_CONNECT_TIMEOUT", "8"))
    printer_read_timeout_seconds: float = float(os.getenv("PRINTER_READ_TIMEOUT", "15"))
    # Development-only joblog debug endpoint. Disable in packaged builds by default.
    printer_joblog_debug: bool = _env_bool(
        "PRINTER_JOBLOG_DEBUG",
        default=not is_packaged_runtime(),
    )


settings = Settings()


def get_printer_credentials(slot: int) -> PrinterCredentialRef:
    if slot not in PRINTER_CREDENTIAL_REFS:
        raise KeyError(f"Unknown printer slot: {slot}")
    return PRINTER_CREDENTIAL_REFS[slot]
