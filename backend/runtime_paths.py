"""Runtime path resolution for development and packaged Electron builds.

Writable data never lives under Program Files / resources / asar.
Override via environment (set by Electron main before spawning the backend):

  PRINTING_RECON_DATA_DIR   — SQLite, uploads, printer downloads
  PRINTING_RECON_LOG_DIR    — application logs
  PRINTING_RECON_ENV_FILE   — backend-only .env with printer credentials
  PRINTING_RECON_FRONTEND_DIST — built Vite assets (served by FastAPI)
"""

from __future__ import annotations

import os
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent


def data_dir() -> Path:
    raw = os.getenv("PRINTING_RECON_DATA_DIR", "").strip()
    if raw:
        path = Path(raw)
    else:
        path = _BACKEND_DIR / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    raw = os.getenv("PRINTING_RECON_LOG_DIR", "").strip()
    if raw:
        path = Path(raw)
    else:
        path = _BACKEND_DIR / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def env_file_candidates() -> list[Path]:
    """Ordered list of .env files to load (later files override earlier)."""
    candidates: list[Path] = []
    explicit = os.getenv("PRINTING_RECON_ENV_FILE", "").strip()
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(_PROJECT_ROOT / ".env")
    candidates.append(_BACKEND_DIR / ".env")
    return candidates


def frontend_dist_dir() -> Path | None:
    raw = os.getenv("PRINTING_RECON_FRONTEND_DIST", "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def is_packaged_runtime() -> bool:
    return bool(os.getenv("PRINTING_RECON_PACKAGED", "").strip())
