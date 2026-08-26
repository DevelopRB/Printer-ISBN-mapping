"""Identifier extraction from printer filenames and free-text fields.

Business rule: List A is the matching authority. Printer filenames may contain
standard ISBNs (978/979…) OR business identifiers (8888…, 1111…, 4444…, etc.).

Rules:
  - Extract the relevant numeric identifier; preserve digits exactly.
  - Normalize only formatting (spaces / hyphens).
  - Do NOT require 978/979 prefix.
  - Do NOT require ISBN-13 checksum validation.
  - Do NOT convert 10-digit (or other) values into 978 ISBN-13.

Does NOT interpret (2), (2 COPIES), F2, PB, BOOK, QC, etc. as quantities.
"""

from __future__ import annotations

import re
from typing import Optional

from services.isbn_validator import normalize_isbn_digits

_PREFIX = re.compile(r"^(?:pub[_-]?|isbn[_:\s-]*)+", re.IGNORECASE)
_LEADING_DIGITS = re.compile(r"^(\d{10,17})")
_DIGIT_RUN = re.compile(r"\d{10,17}")
_NOISE = {"2", "4010"}


def _collect_digits_from(text: str, start: int, need: int = 13) -> str | None:
    """Collect up to `need` digits from text[start:], allowing spaces/hyphens between."""
    digits: list[str] = []
    i = start
    while i < len(text) and len(digits) < need:
        ch = text[i]
        if ch.isdigit():
            digits.append(ch)
        elif ch in "- \t_" and digits:
            pass
        elif digits:
            break
        else:
            break
        i += 1
    if len(digits) >= 10:
        # Prefer a clean 13-digit identifier when available
        if len(digits) >= 13:
            return "".join(digits[:13])
        return "".join(digits)
    return None


def extract_isbn(value) -> Optional[str]:
    """Extract a normalized identifier from a printer filename / free-text value.

    Returns digit-only identifier string, or None if nothing suitable is found.
    Never invents or converts identifiers (no ISBN-10→13 rewriting).
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "null"):
        return None

    # 1) Prefer 978/979 forms when present (compact or hyphenated) — keep digits as-is
    for match in re.finditer(r"(?<!\d)97[89]", text):
        candidate = _collect_digits_from(text, match.start(), need=13)
        if candidate and candidate.startswith(("978", "979")):
            return candidate

    # 2) Leading identifier after stripping Pub_/ISBN prefixes
    stripped = _PREFIX.sub("", text).lstrip(" _-")
    lead = _LEADING_DIGITS.match(stripped)
    if lead:
        candidate = lead.group(1)
        if candidate not in _NOISE:
            return candidate[:13] if len(candidate) > 13 else candidate

    # 3) First substantial digit run in the string
    for match in _DIGIT_RUN.finditer(text):
        candidate = match.group(0)
        if candidate in _NOISE:
            continue
        if len(candidate) >= 13:
            return candidate[:13]
        if len(candidate) >= 10:
            return candidate

    return None


def split_4010_filenames(value) -> list[str]:
    """Split a printer 4010 field into individual filename/document entries.

    Example:
      "978…_F3_QC….pdf | 978…_F3_LB….pdf" → two filenames

    Does not extract identifiers or interpret quantity tokens. Empty input → [].
    """
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "null"):
        return []

    parts = re.split(r"\s*\|\s*", text)
    filenames = [p.strip() for p in parts if p and p.strip()]
    return filenames if filenames else [text]
