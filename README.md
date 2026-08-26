# Printing Reconciliation System

Internal tool to reconcile List A ISBNs (source of truth) against production files from up to three printers.

## Stack

- **Frontend:** React + Vite + TypeScript + Tailwind CSS
- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Files:** `.xlsx`, `.xls`, `.csv`
- **Network printers:** Backend-only HTTP(S) access via env credentials

## Quick start

### Secrets (required for printer connection tests)

```bash
copy .env.example .env
# Edit .env and set PRINTER_1_PASSWORD, PRINTER_2_PASSWORD, PRINTER_3_PASSWORD
```

`.env` is gitignored. Passwords never go to the frontend, database, or API responses.

### Backend

```bash
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The backend host must reach `192.168.2.7`, `192.168.2.218`, and `192.168.2.176`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — API requests are proxied to http://127.0.0.1:8000.

### Tests

```bash
cd backend
.\.venv\Scripts\Activate.ps1
pytest tests/ -v
```

## Production Windows app (Electron)

Operations users install a single EXE — no Node, npm, or Cursor required.

**Build the installer (developers):**

```bat
npm install
npm run dist:win
```

Output: `release\Printing-Reconciliation-Setup-1.0.0.exe`

- Ops guide: [`docs/operations-installation.md`](docs/operations-installation.md)
- Developer packaging guide: [`docs/developer-deployment.md`](docs/developer-deployment.md)

**Electron + packaged FastAPI** starts automatically; UI is served from the local backend. Printer passwords stay in `%APPDATA%\Printing Reconciliation\.env` (never in the renderer).

## Automated reconciliation (Phase 2D)


Open **http://127.0.0.1:5173/automated**

1. Select or upload List A  
2. Select printer(s)  
3. Choose date range  
4. **Fetch & Reconcile** — backend uses Digest auth + `cmd=dl` TSV download (`rs`/`re` = `YYYYMMDD`)  
5. View progress, results, history, and export  

Manual Excel upload remains on the Manual Reconciliation page.

## Network printers (Phase 2A–2C)

| Slot | Default endpoint | Protocol |
|------|------------------|----------|
| 1 | 192.168.2.7:30092 | HTTPS |
| 2 | 192.168.2.218:30092 | HTTPS |
| 3 | 192.168.2.176:30091 | HTTP |

- Credentials: `PRINTER_n_USERNAME` / `PRINTER_n_PASSWORD`
- Self-signed HTTPS: `PRINTER_VERIFY_SSL=false` applies **only** to printer clients
- Job-log protocol (confirmed): see [`docs/printer-joblog-api.md`](docs/printer-joblog-api.md)
- Dev probe: `GET /api/printers/1/joblog/debug` (requires `PRINTER_JOBLOG_DEBUG=true`)
- Automated date-range UI retrieval is **not** enabled yet (Phase 2D+)

## Business rules

- List A is the source of truth.
- Printer filenames are used **only** to extract ISBNs.
- Values like `(2)`, `(2 COPIES)`, `F2`, `PB`, `BOOK`, `QC` are **not** quantities.
- No quantity-matching status is produced.

## Project layout

```
backend/
  api/           # FastAPI routes & schemas
  models/        # SQLAlchemy models
  printers/      # network adapters (connection test; joblog TBD)
  services/      # excel_parser, isbn_*, normalizer, reconciliation, export
  settings.py    # env-based config (no hardcoded passwords)
  tests/
frontend/
  src/components/
  src/pages/
  src/services/
  src/types/
```
