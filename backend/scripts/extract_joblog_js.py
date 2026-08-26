"""Extract JS functions and table structure from joblog HTML."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

html_path = Path(__file__).resolve().parents[1] / "data" / "joblog_probe" / "05_joblog_get.html"
html = html_path.read_text(encoding="utf-8", errors="replace")
out = Path(__file__).resolve().parents[1] / "data" / "joblog_probe"

# Dump all script blocks
scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.I | re.S)
(out / "08_scripts_joined.js").write_text("\n\n/* ---- */\n\n".join(scripts), encoding="utf-8", errors="replace")
print("scripts", len(scripts), "total js chars", sum(len(s) for s in scripts))

# Find function definitions of interest
for name in [
    "onJobLogDL",
    "dlcsv",
    "logToday",
    "updLJS",
    "JobLog",
    "submit",
    "start",
    "end",
    "cmd",
]:
    hits = [m.start() for m in re.finditer(re.escape(name), "\n".join(scripts))]
    print(f"mention {name}: {len(hits)}")

joined = "\n".join(scripts)
for fn in ["onJobLogDL", "dlcsv", "logToday", "function "]:
    pass

# Extract function bodies by naive brace matching for known names
for fn in ["onJobLogDL", "dlcsv", "logToday", "updLJS", "onJobLogSearch", "changeDate", "setDate"]:
    pattern = re.compile(rf"function\s+{fn}\s*\(([^)]*)\)\s*\{{", re.I)
    m = pattern.search(joined)
    if not m:
        # also var fn = function
        pattern2 = re.compile(rf"{fn}\s*=\s*function\s*\(([^)]*)\)\s*\{{", re.I)
        m = pattern2.search(joined)
    if not m:
        print(f"FN {fn}: NOT FOUND")
        continue
    start = m.end() - 1
    depth = 0
    i = start
    while i < len(joined):
        if joined[i] == "{":
            depth += 1
        elif joined[i] == "}":
            depth -= 1
            if depth == 0:
                body = joined[m.start() : i + 1]
                (out / f"09_fn_{fn}.js").write_text(body, encoding="utf-8", errors="replace")
                print(f"FN {fn}: saved {len(body)} chars")
                print(body[:800])
                print("---")
                break
        i += 1

# Table headers / 4010
headers = re.findall(r"<th\b[^>]*>(.*?)</th>", html, flags=re.I | re.S)
headers_clean = [re.sub(r"<[^>]+>", "", h).strip() for h in headers]
print("TH headers:", headers_clean[:40])

# Look for 4010 and Pub_
print("has 4010:", "4010" in html)
print("has Pub_:", "Pub_" in html)
print("has .pdf:", ".pdf" in html.lower())

# sample table rows
rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, flags=re.I | re.S)
print("tr count", len(rows))
for i, row in enumerate(rows[:5]):
    cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, flags=re.I | re.S)
    clean = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
    print(f"row{i}", clean)

# Download form / csv links in HTML
for pat in ["joblogcsv", "download", "csv", "xls", "export", "cmd=", "start=", "end="]:
    for m in re.finditer(rf".{{0,60}}{pat}.{{0,80}}", html, flags=re.I):
        print("CTX", m.group(0).replace("\n", " ")[:140])
