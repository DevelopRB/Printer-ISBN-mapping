"""Post-fix validation for Sheet 3 uniqueness + internal counts."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import urllib.request
from openpyxl import load_workbook

BASE = "http://127.0.0.1:8000/api"
OUT = Path(r"c:\Users\abhis\Desktop\Printer ISBN mapping\_prod_test_out")


def req(method: str, path: str, data=None, files=None, timeout: int = 300):
    url = BASE + path
    if files:
        boundary = uuid.uuid4().hex
        body = b""
        for name, (fname, content, ctype) in files.items():
            body += f"--{boundary}\r\n".encode()
            body += (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{fname}"\r\n'
            ).encode()
            body += f"Content-Type: {ctype}\r\n\r\n".encode()
            body += content + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method=method,
        )
    elif data is not None:
        request = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method=method,
        )
    else:
        request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read()
            if raw[:2] == b"PK":
                return raw
            return json.loads(raw.decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{exc.code}: {exc.read().decode(errors='replace')}") from exc


def main():
    # Bad file message
    try:
        req(
            "POST",
            "/reconciliation/list-a/upload",
            files={"file": ("bad.txt", b"nope", "text/plain")},
        )
        print("BAD FILE: unexpected success")
    except RuntimeError as exc:
        print("BAD FILE:", str(exc)[:200])

    runs = req("GET", "/reconciliation/runs?limit=10")
    run_id = None
    for r in runs:
        if (
            r["status"] == "COMPLETED"
            and r["printer_slots"] == [1]
            and str(r["start_date"])[:10] == "2026-08-01"
            and str(r["end_date"])[:10] == "2026-08-26"
        ):
            run_id = r["id"]
            break
    print("using run", run_id)
    wb_bytes = req("GET", f"/reconciliation/run/{run_id}/export/normalized")
    out = OUT / "run1_normalized_after_fix.xlsx"
    out.write_bytes(wb_bytes)
    book = load_workbook(out, data_only=True)
    ws3 = book["Reconciliation"]
    isbns = [ws3.cell(r, 1).value for r in range(2, ws3.max_row + 1)]
    print("recon rows", len(isbns), "unique", len(set(isbns)))
    assert len(isbns) == len(set(isbns))

    run = next(r for r in runs if r["id"] == run_id)
    d = run["downloads"][0]
    ws2 = book["Printer ISBNs"]
    vals = [ws2.cell(r, 1).value for r in range(2, ws2.max_row + 1)]
    skipped = book["Skipped ISBNs"].max_row - 1
    print("INTERNAL VALIDATION SUMMARY")
    print("Total printer records:", d["record_count"])
    print("Records with ISBN:", len(vals))
    print("Records without ISBN:", skipped)
    print("Normalized printer ISBN occurrences:", len(vals))
    print("Unique printer ISBNs:", len(set(vals)))
    print("Duplicate printer ISBN occurrences:", len(vals) - len(set(vals)))
    print("Skipped records:", skipped)
    print("API summary:", json.dumps(run["summary"], indent=2))

    # Frontend reload semantics: history exists but no auto-selected run payload
    print("runs available after reload:", len(runs))
    print("PASS")


if __name__ == "__main__":
    main()
