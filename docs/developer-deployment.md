# Developer build & deployment guide

## Architecture (packaged)

```
Printing Reconciliation.exe  (Electron)
        │
        ├─ starts PrintingReconciliationAPI.exe  (FastAPI / uvicorn sidecar)
        ├─ serves UI from resources/frontend (via the API)
        └─ credentials in %APPDATA%/Printing Reconciliation/.env  (backend only)
```

Writable runtime data:

| Path | Purpose |
|------|---------|
| `%APPDATA%\Printing Reconciliation\data\` | SQLite, uploads, printer TSV downloads |
| `%APPDATA%\Printing Reconciliation\logs\` | Application + Electron backend logs |
| `%APPDATA%\Printing Reconciliation\.env` | Printer usernames/passwords (never in renderer) |

## Prerequisites (developer machine)

- Node.js 20+ (for Electron / electron-builder)
- Python 3.12 venv at `backend/.venv` with `backend/requirements.txt`
- Project `.env` with printer credentials (used to seed first-run `printer.env`)

## One-command Windows installer

From the project root:

```bat
npm install
npm run dist:win
```

Output:

```
release\Printing-Reconciliation-Setup-1.0.0.exe
```

What the script does:

1. `npm run build:frontend` — Vite production build → `frontend/dist`
2. `npm run build:backend` — PyInstaller onedir → `release/backend/PrintingReconciliationAPI.exe`
3. `electron-builder --win nsis --x64` — NSIS installer

## Development with Electron shell

```bat
npm run build:frontend
npm run electron:dev
```

Uses `backend/.venv` Python + `run_server.py` (not the PyInstaller exe).

## Web-only development (unchanged)

```bat
start-backend.bat
start-frontend.bat
```

Open http://localhost:5173

## Production configuration

Printer IPs/ports remain the seeded defaults (editable in-app on Printers page).

Credentials:

1. Preferred: put real values in project `.env` before `npm run dist:win`  
   → copied to `packaging/printer.env` → seeded into each user’s AppData on first launch.
2. Or edit `%APPDATA%\Printing Reconciliation\.env` after install (IT only).

**Never** put passwords in frontend code or expose them via preload/renderer APIs.

## Code signing

The build is **unsigned** until a Windows Authenticode certificate is available.

Configure later in `package.json` → `build.win.certificateFile` / CSC_* env vars.  
Until then, SmartScreen may warn on first run.

## Clean-machine test checklist

On a PC **without** Node, npm, Cursor, or this repo:

1. Install `Printing-Reconciliation-Setup-1.0.0.exe`
2. Launch from Desktop
3. Confirm UI opens (no terminal windows)
4. Printers → Test Connection (on office LAN)
5. Upload List A → run reconciliation → export Normalized Report
6. Verify sheets: List A ISBNs, Printer ISBNs, Reconciliation, Skipped ISBNs
7. Close app → confirm no leftover `PrintingReconciliationAPI.exe` in Task Manager
8. Reopen and confirm it works again

## Troubleshooting (developers)

| Symptom | Check |
|---------|--------|
| App won’t start | `%APPDATA%\Printing Reconciliation\logs\electron-backend.log` |
| API missing modules | Re-run `npm run build:backend`; inspect PyInstaller warnings |
| Passwords missing | AppData `.env` or rebuild with project `.env` present |
| Port in use | Electron picks next free port from 18765 |

## Tests before packaging

```bat
cd backend
.venv\Scripts\python.exe -m pytest -q
```
