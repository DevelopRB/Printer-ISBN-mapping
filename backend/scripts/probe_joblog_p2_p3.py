"""Phase 2C: light compare of Printer 2 and 3 joblog protocol."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from printers.connection import build_printer_ssl_context
from settings import get_printer_credentials, settings
from database import SessionLocal, init_db
from services.printer_config_service import ensure_network_printer_configs

OUT = Path(__file__).resolve().parents[1] / "data" / "joblog_probe"


def probe(slot: int, protocol: str, host: str, port: int) -> dict:
    creds = get_printer_credentials(slot)
    user = creds.username() or "admin"
    password = creds.password()
    verify = build_printer_ssl_context(verify=settings.printer_verify_ssl) if protocol == "https" else True
    base = f"{protocol}://{host}:{port}"
    auth = httpx.DigestAuth(user, password)
    info = {"slot": slot, "base": base}
    with httpx.Client(base_url=base, verify=verify, timeout=30.0, auth=auth, follow_redirects=True) as c:
        r = c.get("/goform/joblog.cgi")
        info["get_status"] = r.status_code
        info["has_JobLogForm"] = "JobLogForm" in r.text
        info["has_onJobLog"] = "function onJobLog" in r.text
        info["has_joblog_array"] = "joblog[0]" in r.text or "joblog[0] =" in r.text
        info["has_4010_in_clm"] = "4010" in r.text
        info["has_rs_re"] = 'name="rs"' in r.text and 'name="re"' in r.text
        info["has_onJobLogDL"] = "onJobLogDL" in r.text
        # date filter sample
        r2 = c.post(
            "/goform/joblog.cgi",
            data={
                "cmd": "",
                "clm": "1122,4001,4009,4010,1000,1001,1002",
                "viw": "",
                "start": "",
                "end": "",
                "rs": "20260810",
                "re": "20260815",
                "clmmode": "0",
            },
        )
        info["date_post_status"] = r2.status_code
        info["date_post_joblog_count"] = len(re.findall(r"joblog\[\d+\]\s*=", r2.text))
    return info


def main():
    init_db()
    db = SessionLocal()
    rows = ensure_network_printer_configs(db)
    out = []
    for row in rows:
        if row.slot == 1:
            continue  # already fully probed
        out.append(probe(row.slot, row.protocol, row.host, row.port))
    db.close()
    (OUT / "28_printer23_compare.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
