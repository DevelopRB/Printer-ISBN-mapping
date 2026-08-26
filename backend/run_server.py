"""Production server entrypoint (used by Electron / PyInstaller).

No reload. Listens on 127.0.0.1 only. Port from PRINTING_RECON_PORT (default 18765).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# When frozen by PyInstaller, ensure extracted/bundled backend modules resolve.
if getattr(sys, "frozen", False):
    meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    if str(meipass) not in sys.path:
        sys.path.insert(0, str(meipass))
    # Also allow importing from the onedir folder next to the exe
    exe_dir = Path(sys.executable).resolve().parent
    if str(exe_dir) not in sys.path:
        sys.path.insert(0, str(exe_dir))
else:
    backend_root = Path(__file__).resolve().parent
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))


def main() -> None:
    import uvicorn

    host = os.getenv("PRINTING_RECON_HOST", "127.0.0.1")
    port = int(os.getenv("PRINTING_RECON_PORT", "18765"))
    # Import after path setup so runtime_paths / settings see env from Electron
    from main import app  # noqa: WPS433

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
