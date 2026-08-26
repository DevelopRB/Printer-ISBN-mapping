"""Compare manual printer Excel ISBN set vs automated TSV extraction."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from printers.joblog_adapter import JobLogCgiAdapter
from services.isbn_extractor import extract_isbn, split_4010_filenames
from services.normalizer import normalize_list_a, normalize_printer

FALSE_ISBNS = {
    "9781111012144",
    "9781111012526",
    "9781111024987",
    "9781111025779",
    "9784444006248",
    "9788888000244",
    "9788888000343",
    "9788888000398",
    "9788888000411",
    "9788888000480",
    "9788888000749",
    "9788888000855",
    "9788888000862",
    "9788888000923",
    "9788888000930",
    "9788888001166",
    "9788888006888",
    "9788888007113",
    "9788888007366",
    "9788888007380",
}


def extract_from_tsv(path: Path) -> tuple[int, set[str]]:
    adapter = object.__new__(JobLogCgiAdapter)
    records, _meta = JobLogCgiAdapter._parse_tsv(adapter, path.read_bytes())
    isbns: set[str] = set()
    for rec in records:
        filenames = split_4010_filenames(rec.source_filename) or [None]
        for fn in filenames:
            isbn = extract_isbn(fn) if fn else None
            if isbn:
                isbns.add(isbn)
    return len(records), isbns


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "data"

    print("=== Excel inventory ===")
    for f in sorted(root.rglob("*")):
        if f.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
            continue
        try:
            if any(k in f.name.lower() for k in ("list", "pending", "book")):
                r = normalize_list_a(str(f))
                print(f"LISTA  {f.relative_to(root)} rows={r['record_count']} isbns={r['isbn_detected_count']}")
            else:
                r = normalize_printer(str(f))
                uniq = {x["isbn_normalized"] for x in r["records"] if x["isbn_normalized"]}
                print(
                    f"PRINT  {f.relative_to(root)} rows={r['record_count']} "
                    f"uniq={len(uniq)} detected={r['isbn_detected_count']}"
                )
        except Exception as exc:
            print(f"SKIP   {f.relative_to(root)} {type(exc).__name__}: {exc}")

    # Prefer uploads printer1 if it has 1216; else largest printer file
    candidates = []
    for f in root.rglob("*"):
        if f.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
            continue
        if any(k in f.name.lower() for k in ("list", "pending", "book")):
            continue
        try:
            r = normalize_printer(str(f))
            uniq = {x["isbn_normalized"] for x in r["records"] if x["isbn_normalized"]}
            candidates.append((r["record_count"], len(uniq), f, uniq, r))
        except Exception:
            continue
    candidates.sort(reverse=True)

    if not candidates:
        print("No printer Excel found")
        return

    rows, uniq_n, manual_path, manual_isbns, manual_result = candidates[0]
    print()
    print(f"=== MANUAL (selected): {manual_path} ===")
    print(f"Manual rows: {rows}")
    print(f"Manual unique ISBNs: {len(manual_isbns)}")

    tsvs = sorted((root / "printer_downloads").glob("printer_1_*.tsv"))
    if not tsvs:
        print("No printer_1 TSV found")
        return

    # Prefer TSV whose job count matches manual rows
    chosen_tsv = None
    auto_jobs = 0
    auto_isbns: set[str] = set()
    for tsv in reversed(tsvs):
        jobs, isbns = extract_from_tsv(tsv)
        print(f"TSV {tsv.name}: jobs={jobs} uniq={len(isbns)}")
        if jobs == rows:
            chosen_tsv, auto_jobs, auto_isbns = tsv, jobs, isbns
            break
    if chosen_tsv is None:
        chosen_tsv = tsvs[-1]
        auto_jobs, auto_isbns = extract_from_tsv(chosen_tsv)

    print()
    print(f"=== AUTOMATED TSV: {chosen_tsv.name} ===")
    print(f"Automated jobs/records: {auto_jobs}")
    print(f"Automated unique ISBNs: {len(auto_isbns)}")

    common = manual_isbns & auto_isbns
    manual_only = manual_isbns - auto_isbns
    auto_only = auto_isbns - manual_isbns

    print()
    print("=== COMPARISON REPORT ===")
    print(f"Manual ISBNs: {len(manual_isbns)}")
    print(f"Automated ISBNs: {len(auto_isbns)}")
    print(f"Common: {len(common)}")
    print(f"Manual only: {len(manual_only)}")
    print(f"Automated only: {len(auto_only)}")
    print(f"Sets equal: {manual_isbns == auto_isbns}")
    if manual_only:
        print("Manual only sample:", sorted(manual_only)[:15])
    if auto_only:
        print("Automated only sample:", sorted(auto_only)[:15])

    print()
    print("False ISBNs in manual:", sorted(FALSE_ISBNS & manual_isbns))
    print("False ISBNs in automated:", sorted(FALSE_ISBNS & auto_isbns))

    # List A
    for name in ("samples/list_a.xlsx",):
        p = root / name
        if p.exists():
            la = normalize_list_a(str(p))
            la_isbns = {r["isbn_normalized"] for r in la["records"] if r["isbn_normalized"]}
            print()
            print(f"LIST A {name}: records={la['record_count']} unique={len(la_isbns)}")
            print(f"  found in manual: {len(la_isbns & manual_isbns)}")
            print(f"  found in automated: {len(la_isbns & auto_isbns)}")

    for f in root.rglob("*"):
        if f.suffix.lower() not in {".xlsx", ".xls"}:
            continue
        if "pending" in f.name.lower() or f.name.lower().startswith("list"):
            try:
                la = normalize_list_a(str(f))
                if la["record_count"] >= 80:
                    la_isbns = {r["isbn_normalized"] for r in la["records"] if r["isbn_normalized"]}
                    print()
                    print(f"LIST A {f.relative_to(root)}: records={la['record_count']} unique={len(la_isbns)}")
                    print(f"  found in manual: {len(la_isbns & manual_isbns)}")
                    print(f"  found in automated: {len(la_isbns & auto_isbns)}")
            except Exception:
                pass


if __name__ == "__main__":
    main()
