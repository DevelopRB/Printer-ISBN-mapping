"""FastAPI application entrypoint."""

from pathlib import Path
import sys

# Ensure backend root is on sys.path (dev + PyInstaller)
BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from logging_config import logger
from runtime_paths import frontend_dist_dir, is_packaged_runtime
from api.routes import router
from api.network_printers import router as network_printers_router
from api.network_printers import printers_debug_router
from api.automated import router as automated_router
from settings import settings

app = FastAPI(
    title="Printing Reconciliation System",
    version="1.0.0",
    description="Reconcile internal List A ISBNs against printer production files.",
)

_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]
# Electron loads the UI from the local backend origin; also allow common loopback ports.
for port in range(18760, 18780):
    _cors_origins.append(f"http://127.0.0.1:{port}")
    _cors_origins.append(f"http://localhost:{port}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(network_printers_router, prefix="/api")
app.include_router(automated_router, prefix="/api")
if settings.printer_joblog_debug and not is_packaged_runtime():
    app.include_router(printers_debug_router, prefix="/api")


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Printing Reconciliation System started (packaged=%s)", is_packaged_runtime())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please check application logs."},
    )


def _mount_frontend() -> None:
    """Serve the Vite production build from the same origin as /api (Electron)."""
    dist = frontend_dist_dir()
    if not dist:
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    # index.html must be revalidated so an updated app never shows a cached old UI;
    # hashed /assets files are safe to cache.
    no_cache = {"Cache-Control": "no-cache"}

    @app.get("/")
    async def spa_index():
        return FileResponse(dist / "index.html", headers=no_cache)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Never steal API routes
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = dist / full_path
        if candidate.is_file():
            return FileResponse(candidate, headers=no_cache)
        return FileResponse(dist / "index.html", headers=no_cache)

    logger.info("Serving frontend from %s", dist)


_mount_frontend()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
