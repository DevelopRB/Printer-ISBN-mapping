"""Identifier / ISBN normalization helpers.

Checksum validators remain available for optional diagnostic use.
Matching does NOT require ISBN-13 checksum or 978/979 prefix.
Identifiers are never auto-converted (no ISBN-10 → ISBN-13 rewrite).
"""

from __future__ import annotations


def normalize_isbn_digits(value: str) -> str:
    """Remove spaces and hyphens; keep digits and X/x."""
    cleaned = []
    for ch in value:
        if ch.isdigit():
            cleaned.append(ch)
        elif ch in ("X", "x") and not cleaned:
            continue
        elif ch in ("X", "x"):
            cleaned.append("X")
    return "".join(cleaned)


def is_valid_isbn13(isbn: str) -> bool:
    """Standard ISBN-13 checksum check (978/979 only). Diagnostic — not a match gate."""
    digits = normalize_isbn_digits(isbn)
    if len(digits) != 13 or not digits.isdigit():
        return False
    if not digits.startswith(("978", "979")):
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    check = (10 - (total % 10)) % 10
    return check == int(digits[12])


def is_valid_isbn10(isbn: str) -> bool:
    """Standard ISBN-10 checksum check. Diagnostic — not used for conversion."""
    digits = normalize_isbn_digits(isbn)
    if len(digits) != 10:
        return False
    body, check = digits[:9], digits[9]
    if not body.isdigit():
        return False
    if not (check.isdigit() or check == "X"):
        return False
    total = sum(int(d) * (10 - i) for i, d in enumerate(body))
    expected = 11 - (total % 11)
    if expected == 11:
        expected_char = "0"
    elif expected == 10:
        expected_char = "X"
    else:
        expected_char = str(expected)
    return check == expected_char


def isbn10_to_isbn13(isbn10: str) -> str | None:
    """Optional conversion helper — NOT used by printer/List A matching."""
    digits = normalize_isbn_digits(isbn10)
    if not is_valid_isbn10(digits):
        return None
    core = "978" + digits[:9]
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(core))
    check = (10 - (total % 10)) % 10
    return core + str(check)


def validate_and_normalize(isbn: str | None) -> str | None:
    """Normalize a List A / cell identifier for matching.

    - Strips spaces/hyphens
    - Keeps the digit string as-is (no checksum gate, no 978 rewrite)
    - Returns None only when no usable identifier digits are present
    """
    if isbn is None:
        return None
    text = str(isbn).strip()
    if not text:
        return None

    digits = normalize_isbn_digits(text)
    if len(digits) >= 10 and digits.isdigit():
        return digits

    # Fallback: extract from free-text / embedded forms
    from services.isbn_extractor import extract_isbn

    return extract_isbn(text)
