"""Extract onJobLog and data variables from joblog page JS."""

from __future__ import annotations

import json
import re
from pathlib import Path

out = Path(__file__).resolve().parents[1] / "data" / "joblog_probe"
joined = (out / "08_scripts_joined.js").read_text(encoding="utf-8", errors="replace")

# Find onJobLog function
for fn in ["onJobLog", "updateLogJumpSelecter", "updateJoblogDownloadLink", "makeCSV", "buildCSV"]:
    m = re.search(rf"function\s+{fn}\s*\(([^)]*)\)\s*\{{", joined)
    if not m:
        (out / f"11_missing_{fn}.txt").write_text("not found", encoding="utf-8")
        continue
    start = m.end() - 1
    depth = 0
    i = start
    while i < len(joined):
        ch = joined[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = joined[m.start() : i + 1]
                (out / f"11_fn_{fn}.js").write_text(body, encoding="utf-8", errors="replace")
                break
        i += 1

# Variable assignments for logstart/logend/logtotal/logmax/csvtxt/L
vars_of_interest = {}
for name in ["logstart", "logend", "logtotal", "logmax", "csvtxt", "From", "To", "Count"]:
    ms = list(re.finditer(rf"\b{name}\s*=\s*([^;]+);", joined))
    vars_of_interest[name] = [m.group(0)[:200] for m in ms[:10]]

(out / "12_var_assignments.json").write_text(json.dumps(vars_of_interest, indent=2), encoding="utf-8")

# Find array L definition - often var L = [ ... ] or L[i]
# Look for lines with Pub_ or 978 to see structure
isbn_lines = []
for line in joined.splitlines():
    if "Pub_" in line or "978" in line or "4010" in line:
        isbn_lines.append(line.strip()[:300])
(out / "13_isbn_lines.txt").write_text("\n".join(isbn_lines[:100]), encoding="utf-8", errors="replace")

# Find how L is populated - search for L =
l_assigns = re.findall(r".{0,40}\bL\s*=\s*.{0,80}", joined)
(out / "14_L_assigns.txt").write_text("\n".join(l_assigns[:50]), encoding="utf-8", errors="replace")

# Look for template that builds table cells - column indices
col_hints = re.findall(r"L\[i\]\[(\d+)\]", joined)
(out / "15_L_indices.txt").write_text(
    "indices=" + ",".join(sorted(set(col_hints), key=lambda x: int(x))) + "\n" + "\n".join(f"L[i][{i}] count" for i in sorted(set(col_hints), key=int)),
    encoding="utf-8",
)

# Also search L[n] style in string building
for pat in [r"L\[i\]\[(\d+)\]", r"job\[(\d+)\]", r"log\[(\d+)\]"]:
    pass

# Dump first 200 lines of script for structure
(out / "16_script_head.txt").write_text("\n".join(joined.splitlines()[:250]), encoding="utf-8", errors="replace")

print("onJobLog saved", (out / "11_fn_onJobLog.js").exists())
print("isbn lines", len(isbn_lines))
print("L indices", sorted(set(col_hints), key=int)[:30])
print("logstart assigns", vars_of_interest.get("logstart"))
print("logend assigns", vars_of_interest.get("logend"))
