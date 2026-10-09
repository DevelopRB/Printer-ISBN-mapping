import { normalizeSearchIsbn } from './isbnNormalize'
import type {
  IsbnSearchResult,
  IsbnSearchStatus,
  PrinterSearchOccurrence,
  RunSearchData,
} from '../types'

export type IsbnSearchIndex = {
  runId: number
  startDate: string | null
  endDate: string | null
  listAIndex: Set<string>
  /** normalized ISBN → all printer occurrences (not deduplicated) */
  printerIndex: Map<string, PrinterSearchOccurrence[]>
  occurrenceCount: number
  listACount: number
}

export function buildIsbnSearchIndex(data: RunSearchData): IsbnSearchIndex {
  const listAIndex = new Set(
    data.list_a_isbns
      .map((x) => normalizeSearchIsbn(String(x)) || String(x).trim())
      .filter(Boolean),
  )
  const printerIndex = new Map<string, PrinterSearchOccurrence[]>()

  for (const occ of data.printer_occurrences) {
    const key = normalizeSearchIsbn(String(occ.isbn || '')) || String(occ.isbn || '').trim()
    if (!key) continue
    const bucket = printerIndex.get(key)
    if (bucket) bucket.push(occ)
    else printerIndex.set(key, [occ])
  }

  return {
    runId: data.run_id,
    startDate: data.start_date ?? null,
    endDate: data.end_date ?? null,
    listAIndex,
    printerIndex,
    occurrenceCount: data.printer_occurrences.length,
    listACount: listAIndex.size,
  }
}

function resolveStatus(listA: boolean, printer: boolean): IsbnSearchStatus {
  if (listA && printer) return 'PRESENT'
  if (listA && !printer) return 'NOT FOUND'
  if (!listA && printer) return 'FOUND IN PRINTER DATA'
  return 'NOT FOUND'
}

export function searchIsbnIndex(
  index: IsbnSearchIndex,
  rawQuery: string,
): IsbnSearchResult | { error: string } {
  const trimmed = String(rawQuery).trim()
  if (!trimmed) return { error: 'Enter an ISBN or identifier to search.' }

  const normalized = normalizeSearchIsbn(trimmed)
  if (!normalized) return { error: 'Could not read an identifier from that input.' }

  const listA = index.listAIndex.has(normalized)
  const occurrences = index.printerIndex.get(normalized) ?? []
  const printer = occurrences.length > 0

  return {
    query: trimmed,
    normalizedIsbn: normalized,
    listA,
    printer,
    status: resolveStatus(listA, printer),
    occurrences,
  }
}
