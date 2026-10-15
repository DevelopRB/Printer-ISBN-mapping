"""Save printer credentials entered in the app to this computer's backend-only .env.

Values are written to the env file and applied to the running process; they are never
logged or returned by any API.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from runtime_paths import env_file_candidates
from settings import get_printer_credentials


def credentials_env_path() -> Path:
    """The .env that wins at startup: Electron's userData file, else the last existing dev file."""
    explicit = os.getenv("PRINTING_RECON_ENV_FILE", "").strip()
    if explicit:
        return Path(explicit)
    candidates = env_file_candidates()
    existing = [p for p in candidates if p.is_file()]
    return existing[-1] if existing else candidates[0]


def _quote(value: str) -> str:
    # python-dotenv single-quoted values only unescape \\ and \'
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _upsert_env_lines(lines: list[str], updates: dict[str, str]) -> list[str]:
    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        key = match.group(1) if match else None
        if key in remaining:
            out.append(f"{key}={_quote(remaining.pop(key))}")
        else:
            out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={_quote(value)}")
    return out


def save_printer_credentials(slot: int, username: str, password: str | None) -> None:
    """Persist username (and password when given) for a printer slot.

    A blank/None password keeps the currently saved one.
    """
    creds = get_printer_credentials(slot)
    username = username.strip()
    if not username:
        raise ValueError("Enter the printer username.")
    if len(username) > 100 or any(c in username for c in "\r\n"):
        raise ValueError("The username is not valid.")
    if password and (len(password) > 200 or any(c in password for c in "\r\n")):
        raise ValueError("The password is not valid.")
    if not password and not creds.has_password_configured():
        raise ValueError("Enter the printer password.")

    updates = {creds.username_env: username}
    if password:
        updates[creds.password_env] = password

    path = credentials_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    content = "\n".join(_upsert_env_lines(lines, updates)) + "\n"

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)

    for key, value in updates.items():
        os.environ[key] = value
