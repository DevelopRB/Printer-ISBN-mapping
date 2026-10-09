/**
 * Mirror of backend services.isbn_validator.normalize_isbn_digits.
 * Keep in sync — search keys must match reconciliation normalization.
 */
export function normalizeIsbnDigits(value: string): string {
  const cleaned: string[] = []
  for (const ch of value) {
    if (/\d/.test(ch)) {
      cleaned.push(ch)
    } else if ((ch === 'X' || ch === 'x') && cleaned.length === 0) {
      continue
    } else if (ch === 'X' || ch === 'x') {
      cleaned.push('X')
    }
  }
  return cleaned.join('')
}

/** Trim + same digit normalization used for List A / printer matching keys. */
export function normalizeSearchIsbn(raw: string): string | null {
  const text = String(raw).trim()
  if (!text) return null
  const digits = normalizeIsbnDigits(text)
  return digits || null
}

/** Practical batch size for Operations paste-from-Excel workflows. */
export const MAX_BATCH_ISBNS = 1000

/**
 * Parse pasted multi-ISBN text (Excel columns, CSV, commas, spaces, tabs).
 * Returns entered tokens (valid only) and unique normalized IDs in input order.
 */
export function parseMultiIsbnInput(raw: string): {
  enteredCount: number
  uniqueIsbns: string[]
  invalidSkipped: number
} {
  const text = String(raw || '')
  if (!text.trim()) {
    return { enteredCount: 0, uniqueIsbns: [], invalidSkipped: 0 }
  }

  // Split on newlines / commas / semicolons; keep tabs for column handling per line
  const chunks = text
    .split(/[\n\r,;]+/)
    .map((c) => c.trim())
    .filter(Boolean)

  const uniqueIsbns: string[] = []
  const seen = new Set<string>()
  let enteredCount = 0
  let invalidSkipped = 0

  for (const chunk of chunks) {
    // Excel multi-column paste: take first column (tab or 2+ spaces)
    let token = chunk
    if (token.includes('\t')) {
      token = token.split('\t')[0]?.trim() || ''
    } else {
      const multiSpace = token.split(/\s{2,}/)[0]?.trim()
      if (multiSpace) token = multiSpace
    }
    // Also handle "ISBN BookName" on one space if first token looks like digits
    const firstWord = token.split(/\s+/)[0] || ''
    if (/^[\dXx-]{10,}$/.test(firstWord.replace(/-/g, ''))) {
      token = firstWord
    }

    if (!token) continue

    const normalized = normalizeSearchIsbn(token)
    const digitLen = normalized ? normalized.replace(/X/gi, '').length : 0
    if (!normalized || digitLen < 10) {
      invalidSkipped += 1
      continue
    }

    enteredCount += 1
    if (seen.has(normalized)) continue
    seen.add(normalized)
    uniqueIsbns.push(normalized)
  }

  return { enteredCount, uniqueIsbns, invalidSkipped }
}
