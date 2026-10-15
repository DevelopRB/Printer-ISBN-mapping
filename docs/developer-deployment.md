# Developer build & deployment guide

## Architecture (packaged)

```
Printing Reconciliation.exe  (Electron)
        │
        ├─ starts PrintingReconciliationAPI.exe  (FastAPI / uvicorn sidecar)
        ├─ serves UI from resources/frontend (via the API)
        └─ credentials in %APPDATA%/printing-reconciliation/.env  (backend only)
```

Writable runtime data:

| Path | Purpose |
|------|---------|
| `%APPDATA%\printing-reconciliation\data\` | SQLite, uploads, printer TSV downloads |
| `%APPDATA%\printing-reconciliation\logs\` | Application + Electron backend logs |
| `%APPDATA%\printing-reconciliation\.env` | Printer usernames/passwords (never in renderer) |

## Prerequisites (developer machine)

- Node.js 20+ (for Electron / electron-builder)
- Python 3.12 venv at `backend/.venv` with `backend/requirements.txt`
- Project `.env` with printer credentials for local development only (never packaged)

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
3. `npm run check:secrets` — fails the build if any packaged file contains an env file or a
   PASSWORD / SECRET / TOKEN / API_KEY value
4. `electron-builder --win nsis --x64` — NSIS installer

## Releasing updates to the team (auto-update)

Installed apps check GitHub Releases of `DevelopRB/Printer-ISBN-mapping` on launch and every
4 hours. A newer version downloads in the background; users get a **Restart Now / Later**
prompt, and "Later" installs it when the app is closed. Data, logs and the AppData `.env`
are kept. Update failures (offline, GitHub unreachable) are only logged to
`%APPDATA%\printing-reconciliation\logs\updater.log`.

One-time setup on the developer machine:

1. Create a GitHub token that can write releases to this repo — either a fine-grained token
   (repository `Printer-ISBN-mapping`, permission **Contents: Read and write**) or a classic
   token with the `public_repo` scope.
2. Save it as a user environment variable (then open a new terminal):

   ```powershell
   [Environment]::SetEnvironmentVariable("GH_TOKEN", "<your token>", "User")
   ```

The token is used only to upload; it is never packaged into the app (the repo is public, so
installed apps download updates without credentials).

Each release:

```bat
npm run release            :: 1.2.3 -> 1.2.4 (fixes / small changes)
npm run release -- minor   :: 1.2.3 -> 1.3.0 (new features)
```

The script bumps the version, builds, runs the secret check and publishes the installer,
`latest.yml` and blockmap to a GitHub Release. If any step fails the version is restored and
nothing is published. Afterwards commit and push `package.json` / `package-lock.json`.

Apps installed from a build **before** auto-update was added (1.0.0) cannot update
themselves; each teammate installs the first auto-updating release once from
https://github.com/DevelopRB/Printer-ISBN-mapping/releases/latest.

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

The installer never contains credentials. On first launch each user's
`%APPDATA%\printing-reconciliation\.env` is seeded from the bundled `env.example` (empty
passwords); IT then fills in the passwords on that machine.

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
| App won’t start | `%APPDATA%\printing-reconciliation\logs\electron-backend.log` |
| API missing modules | Re-run `npm run build:backend`; inspect PyInstaller warnings |
| Passwords missing | AppData `.env` or rebuild with project `.env` present |
| Port in use | Electron picks next free port from 18765 |

## Tests before packaging

```bat
cd backend
.venv\Scripts\python.exe -m pytest -q
```
