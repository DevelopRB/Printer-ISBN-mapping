"""Offline tests for joblog TSV/HTML parsing (from captured Printer 1 responses)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from printers.joblog_adapter import JobLogCgiAdapter, format_yyyymmdd


PROBE = Path(__file__).resolve().parents[1] / "data" / "joblog_probe"


def _adapter() -> JobLogCgiAdapter:
    return JobLogCgiAdapter(
        slot=1,
        name="Printer 1",
        protocol="https",
        host="192.168.2.7",
        port=30092,
    )


def test_format_yyyymmdd():
    from datetime import date

    assert format_yyyymmdd(date(2026, 8, 1)) == "20260801"
    assert format_yyyymmdd("2026-08-26") == "20260826"


def test_parse_tsv_download_has_4010_and_date():
    path = PROBE / "25_download_dl_daterange.bin"
    if not path.exists():
        return  # skip if probe artifacts absent
    adapter = _adapter()
    records, meta = adapter._parse_tsv(path.read_bytes())  # noqa: SLF001
    assert len(records) > 100
    assert "4010" in meta["header"]
    assert any(r.source_filename and "pdf" in r.source_filename.lower() for r in records[:20])
    assert any(r.printer_date and r.printer_date.startswith("2026-08-") for r in records[:50])


def test_parse_html_joblog_array():
    path = PROBE / "05_joblog_get.html"
    if not path.exists():
        return
    adapter = _adapter()
    html = path.read_text(encoding="utf-8", errors="replace")
    records, meta = adapter._parse_html_joblog_js(html)  # noqa: SLF001
    assert len(records) >= 50
    assert meta.get("logtotal") is not None
    assert any(r.source_filename and "Pub_" in r.source_filename for r in records)
