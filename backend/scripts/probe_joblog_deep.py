"""Phase 2C deep probe: Digest auth, date-range POST, download cmd=dl."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from printers.connection import build_printer_ssl_context
from settings import get_printer_credentials, settings

OUT = Path(__file__).resolve().parents[1] / "data" / "joblog_probe"
OUT.mkdir(parents=True, exist_ok=True)

# Column map from onJobLog() JS (confirmed from printer page)
CLM = (
    "1122,4001,4009,4010,4005,1630,1034,1091,2003,"
    "1000,1001,1002,1003,1004,1005,"
    "1285,1286,1287,1288,1289,1290,"
    "1006,1007,1008,1009,1010,1011,"
    "1041,1045,1022,4005,1047,2025,2106,"
    "1271,1272,1273,1274,1275,1401,"
    "1610,1611,1612,1613,1614,1615,1616,"
    "1617,1618,1619,1620,1276,1277,1278,1279,1621"
)


def main():
    creds = get_printer_credentials(1)
    user = creds.username() or "admin"
    password = creds.password()
    verify = build_printer_ssl_context(verify=settings.printer_verify_ssl)
    base = "https://192.168.2.7:30092"

    results = {"auth_tests": [], "posts": []}

    # Compare Basic vs Digest
    for label, auth in [
        ("basic", (user, password)),
        ("digest", httpx.DigestAuth(user, password)),
    ]:
        with httpx.Client(base_url=base, verify=verify, timeout=30.0, auth=auth, follow_redirects=True) as c:
            r = c.get("/goform/joblog.cgi")
            results["auth_tests"].append(
                {
                    "auth": label,
                    "status": r.status_code,
                    "len": len(r.content),
                    "www_authenticate_request_was": "see noauth earlier = Digest",
                }
            )

    auth = httpx.DigestAuth(user, password)
    with httpx.Client(base_url=base, verify=verify, timeout=60.0, auth=auth, follow_redirects=True) as c:
        # Default page
        r0 = c.get("/goform/joblog.cgi")
        (OUT / "20_default_get.html").write_bytes(r0.content)
        logstart = re.search(r"logstart\s*=\s*(\d+)", r0.text)
        logend = re.search(r"logend\s*=\s*(\d+)", r0.text)
        logtotal = re.search(r"logtotal\s*=\s*(\d+)", r0.text)
        results["default_window"] = {
            "logstart": logstart.group(1) if logstart else None,
            "logend": logend.group(1) if logend else None,
            "logtotal": logtotal.group(1) if logtotal else None,
            "joblog_count": len(re.findall(r"joblog\[\d+\]\s*=", r0.text)),
        }

        # Find calcDays / date format hints
        calc = re.search(r"function\s+calcDays\s*\((.*?)\)\s*\{(.*?)\n\}", r0.text, re.S)
        if calc:
            (OUT / "21_calcDays.js").write_text(calc.group(0), encoding="utf-8", errors="replace")

        # Date-range POSTs — digits only as UI does replace(/\D/g,"")
        date_cases = [
            ("20260801", "20260826"),
            ("20260810", "20260815"),
            ("260801", "260826"),  # if YYMMDD
        ]
        for rs, re_ in date_cases:
            data = {
                "cmd": "",
                "clm": CLM,
                "viw": "",
                "start": "",
                "end": "",
                "rs": rs,
                "re": re_,
                "clmmode": "0",
            }
            r = c.post("/goform/joblog.cgi", data=data)
            count = len(re.findall(r"joblog\[\d+\]\s*=", r.text))
            # sample first filename + date fields
            sample = re.search(r'joblog\[0\]\s*=\s*"([^"]*)"', r.text)
            sample_fields = sample.group(1).split("\t") if sample else []
            results["posts"].append(
                {
                    "kind": "date_range",
                    "rs": rs,
                    "re": re_,
                    "status": r.status_code,
                    "len": len(r.content),
                    "joblog_count": count,
                    "sample_filename": sample_fields[3] if len(sample_fields) > 3 else None,
                    "sample_date_yy_mm_dd": sample_fields[9:12] if len(sample_fields) > 11 else None,
                    "content_type": r.headers.get("content-type"),
                }
            )
            (OUT / f"22_date_{rs}_{re_}.html").write_bytes(r.content)

        # Index-window POST (pagination style)
        ls = results["default_window"]["logstart"]
        le = results["default_window"]["logend"]
        if ls and le:
            data = {
                "cmd": "",
                "clm": CLM,
                "viw": "",
                "start": ls,
                "end": le,
                "rs": "",
                "re": "",
                "clmmode": "0",
            }
            r = c.post("/goform/joblog.cgi", data=data)
            results["posts"].append(
                {
                    "kind": "index_window",
                    "start": ls,
                    "end": le,
                    "status": r.status_code,
                    "joblog_count": len(re.findall(r"joblog\[\d+\]\s*=", r.text)),
                    "len": len(r.content),
                }
            )
            (OUT / "23_index_window.html").write_bytes(r.content)

        # Download cmd=dl for current window
        if ls and le:
            data = {
                "cmd": "dl",
                "clm": CLM,
                "viw": "",
                "start": ls,
                "end": le,
                "rs": "",
                "re": "",
                "clmmode": "0",
            }
            r = c.post("/goform/joblog.cgi", data=data)
            ctype = r.headers.get("content-type", "")
            cd = r.headers.get("content-disposition", "")
            results["posts"].append(
                {
                    "kind": "download_dl",
                    "start": ls,
                    "end": le,
                    "status": r.status_code,
                    "content_type": ctype,
                    "content_disposition": cd,
                    "len": len(r.content),
                    "body_preview_ascii": r.content[:200].decode("utf-8", errors="replace"),
                }
            )
            (OUT / "24_download_dl.bin").write_bytes(r.content)

        # Download with date range
        data = {
            "cmd": "dl",
            "clm": CLM,
            "viw": "",
            "start": "",
            "end": "",
            "rs": "20260801",
            "re": "20260826",
            "clmmode": "0",
        }
        r = c.post("/goform/joblog.cgi", data=data)
        results["posts"].append(
            {
                "kind": "download_dl_date_range",
                "rs": "20260801",
                "re": "20260826",
                "status": r.status_code,
                "content_type": r.headers.get("content-type"),
                "content_disposition": r.headers.get("content-disposition"),
                "len": len(r.content),
                "body_preview_ascii": r.content[:300].decode("utf-8", errors="replace"),
            }
        )
        (OUT / "25_download_dl_daterange.bin").write_bytes(r.content)

        # GET with rs/re query (UI builds ./joblog.cgi?rs=&re= before POST via onJobLog)
        r = c.get("/goform/joblog.cgi", params={"rs": "20260810", "re": "20260815"})
        results["posts"].append(
            {
                "kind": "get_query_rs_re",
                "status": r.status_code,
                "joblog_count": len(re.findall(r"joblog\[\d+\]\s*=", r.text)),
                "len": len(r.content),
            }
        )
        (OUT / "26_get_rs_re.html").write_bytes(r.content)

    (OUT / "27_deep_probe_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
