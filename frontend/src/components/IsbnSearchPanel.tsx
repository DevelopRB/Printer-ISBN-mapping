import { useId, useMemo, useState } from 'react'
import { CheckCircle2, Copy, Download, Loader2, Search, X, XCircle } from 'lucide-react'
import { directIsbnSearch, directMultiIsbnSearch, exportSearchResults } from '../services/api'
import type { SearchResultExportRow } from '../services/api'
import { MAX_BATCH_ISBNS, normalizeSearchIsbn, parseMultiIsbnInput } from '../lib/isbnNormalize'
import { usePrinterHealth } from '../lib/printerHealth'
import type {
  DirectBatchItemResponse,
  DirectIsbnSearchResponse,
  DirectMultiIsbnSearchResponse,
  IsbnSearchResult,
  PrinterSearchOccurrence,
} from '../types'

const RECENT_KEY = 'printing-recon-isbn-recent-v3'
const RECENT_LIMIT = 8

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

type SearchMode = 'single' | 'multiple'
type BatchFilter = 'ALL' | 'FOUND' | 'NOT FOUND' | 'CONNECTION ISSUES'
type PrintDateSort = 'latest' | 'oldest' | 'monthAsc' | 'monthDesc'

const PRINT_DATE_SORT_OPTIONS: { value: PrintDateSort; label: string }[] = [
  { value: 'latest', label: 'Latest to Oldest' },
  { value: 'oldest', label: 'Oldest to Latest' },
  { value: 'monthAsc', label: 'January → December' },
  { value: 'monthDesc', label: 'December → January' },
]

type RecentSearch = {
  mode: SearchMode
  isbn: string
  multiText?: string
  uniqueCount?: number
  startDate: string
  endDate: string
}

function todayISO() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function daysAgoISO(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function clampToToday(value: string): string {
  const today = todayISO()
  return value > today ? today : value
}

function formatPrintDate(value: string | null | undefined): string {
  if (!value) return '—'
  const text = String(value).trim()
  if (text.length >= 10 && text[4] === '-' && text[7] === '-') {
    const y = Number(text.slice(0, 4))
    const m = Number(text.slice(5, 7))
    const d = Number(text.slice(8, 10))
    if (m >= 1 && m <= 12 && d >= 1) return `${String(d).padStart(2, '0')}-${MONTHS[m - 1]}-${y}`
  }
  if (text.length >= 10 && text[4] === '/' && text[7] === '/') {
    const y = Number(text.slice(0, 4))
    const m = Number(text.slice(5, 7))
    const d = Number(text.slice(8, 10))
    if (m >= 1 && m <= 12 && d >= 1) return `${String(d).padStart(2, '0')}-${MONTHS[m - 1]}-${y}`
  }
  return text
}

/** Parse printer Print Date into comparable parts. Returns null when missing/invalid. */
function parsePrintDateParts(
  value: string | null | undefined,
): { year: number; month: number; day: number; ordinal: number } | null {
  if (!value) return null
  const text = String(value).trim()
  if (!text) return null

  // ISO / slash: YYYY-MM-DD or YYYY/MM/DD
  if (text.length >= 10 && (text[4] === '-' || text[4] === '/') && (text[7] === '-' || text[7] === '/')) {
    const year = Number(text.slice(0, 4))
    const month = Number(text.slice(5, 7))
    const day = Number(text.slice(8, 10))
    if (
      Number.isFinite(year) &&
      month >= 1 &&
      month <= 12 &&
      day >= 1 &&
      day <= 31
    ) {
      return { year, month, day, ordinal: year * 10000 + month * 100 + day }
    }
  }

  // Display form: DD-Mon-YYYY (e.g. 27-Aug-2026)
  const monMatch = text.match(/^(\d{1,2})-([A-Za-z]{3})-(\d{4})$/)
  if (monMatch) {
    const day = Number(monMatch[1])
    const monIdx = MONTHS.findIndex((m) => m.toLowerCase() === monMatch[2].toLowerCase())
    const year = Number(monMatch[3])
    if (monIdx >= 0 && day >= 1 && day <= 31 && Number.isFinite(year)) {
      const month = monIdx + 1
      return { year, month, day, ordinal: year * 10000 + month * 100 + day }
    }
  }

  return null
}

function compareByPrintDateSort(
  aDate: string | null | undefined,
  bDate: string | null | undefined,
  mode: PrintDateSort,
  aIndex: number,
  bIndex: number,
): number {
  const a = parsePrintDateParts(aDate)
  const b = parsePrintDateParts(bDate)

  // Undated (NOT FOUND / CONNECTION ISSUE / missing) always after dated rows
  if (!a && !b) return aIndex - bIndex
  if (!a) return 1
  if (!b) return -1

  if (mode === 'latest') {
    if (b.ordinal !== a.ordinal) return b.ordinal - a.ordinal
    return aIndex - bIndex
  }
  if (mode === 'oldest') {
    if (a.ordinal !== b.ordinal) return a.ordinal - b.ordinal
    return aIndex - bIndex
  }
  if (mode === 'monthAsc') {
    if (a.month !== b.month) return a.month - b.month
    if (a.ordinal !== b.ordinal) return a.ordinal - b.ordinal
    return aIndex - bIndex
  }
  // monthDesc
  if (a.month !== b.month) return b.month - a.month
  if (a.ordinal !== b.ordinal) return b.ordinal - a.ordinal
  return aIndex - bIndex
}

function sortOccurrences(
  occurrences: PrinterSearchOccurrence[],
  mode: PrintDateSort,
): PrinterSearchOccurrence[] {
  return occurrences
    .map((o, index) => ({ o, index }))
    .sort((a, b) => compareByPrintDateSort(a.o.print_date, b.o.print_date, mode, a.index, b.index))
    .map(({ o }) => o)
}

function PrintDateSortControl({
  id,
  value,
  onChange,
}: {
  id: string
  value: PrintDateSort
  onChange: (next: PrintDateSort) => void
}) {
  return (
    <label className="inline-flex items-center gap-2 text-xs text-slate-600" htmlFor={id}>
      <span className="font-medium whitespace-nowrap">Sort by Print Date</span>
      <select
        id={id}
        className="ui-input h-9 min-w-[11.5rem] py-1.5 text-xs font-medium text-slate-800 transition-colors duration-150"
        value={value}
        onChange={(e) => onChange(e.target.value as PrintDateSort)}
      >
        {PRINT_DATE_SORT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function shortPrinterLabel(name: string, slot: number): string {
  const match = name.match(/^Printer\s+\d+/i)
  if (match) return match[0]
  return name || `Printer ${slot}`
}

function loadRecent(): RecentSearch[] {
  try {
    const raw = sessionStorage.getItem(RECENT_KEY)
    if (!raw) {
      // Migrate v2 single-ISBN recent entries if present
      const legacy = sessionStorage.getItem('printing-recon-isbn-recent-v2')
      if (!legacy) return []
      const parsed = JSON.parse(legacy) as unknown
      if (!Array.isArray(parsed)) return []
      return parsed
        .filter(
          (x): x is { isbn: string; startDate: string; endDate: string } =>
            !!x &&
            typeof x === 'object' &&
            typeof (x as { isbn?: string }).isbn === 'string' &&
            typeof (x as { startDate?: string }).startDate === 'string' &&
            typeof (x as { endDate?: string }).endDate === 'string',
        )
        .map((x) => ({
          mode: 'single' as const,
          isbn: x.isbn,
          startDate: x.startDate,
          endDate: x.endDate,
        }))
        .slice(0, RECENT_LIMIT)
    }
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter((x): x is RecentSearch => {
        if (!x || typeof x !== 'object') return false
        const e = x as RecentSearch
        return (
          (e.mode === 'single' || e.mode === 'multiple') &&
          typeof e.isbn === 'string' &&
          typeof e.startDate === 'string' &&
          typeof e.endDate === 'string'
        )
      })
      .slice(0, RECENT_LIMIT)
  } catch {
    return []
  }
}

function pushRecent(entry: RecentSearch): RecentSearch[] {
  const next = [
    entry,
    ...loadRecent().filter((x) => {
      if (entry.mode === 'multiple') {
        return !(
          x.mode === 'multiple' &&
          x.uniqueCount === entry.uniqueCount &&
          x.startDate === entry.startDate &&
          x.endDate === entry.endDate &&
          x.multiText === entry.multiText
        )
      }
      return !(
        x.mode === 'single' &&
        x.isbn === entry.isbn &&
        x.startDate === entry.startDate &&
        x.endDate === entry.endDate
      )
    }),
  ].slice(0, RECENT_LIMIT)
  try {
    sessionStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch {
    /* ignore quota */
  }
  return next
}

function statusClasses(status: string): string {
  if (status === 'PRESENT' || status === 'FOUND' || status === 'FOUND IN PRINTER DATA') {
    return 'bg-green-100 text-green-900 border-green-200'
  }
  if (status === 'CONNECTION ISSUE' || status === 'CONNECTION ISSUES') {
    return 'bg-orange-100 text-orange-950 border-orange-200'
  }
  return 'bg-amber-100 text-amber-950 border-amber-200'
}

function displayBatchStatus(status: string): string {
  if (status === 'PRESENT' || status === 'FOUND IN PRINTER DATA') return 'FOUND'
  if (status === 'CONNECTION ISSUE') return 'CONNECTION ISSUE'
  return 'NOT FOUND'
}

function resultTitle(result: IsbnSearchResult): string {
  if (result.printer) return 'ISBN FOUND'
  return 'ISBN NOT FOUND'
}

function listALabel(listA: boolean | null): string {
  if (listA === null) return 'N/A'
  return listA ? 'YES' : 'NO'
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

function formatOccurrenceLine(o: PrinterSearchOccurrence): string {
  return [
    formatPrintDate(o.print_date),
    o.job_end || '—',
    o.print_start || '—',
    o.job_accept || '—',
    o.result || '—',
    `Requested ${o.set_number ?? '—'}`,
    `Printed ${o.output_set ?? '—'}`,
    shortPrinterLabel(o.printer_name, o.printer_slot),
    o.source_filename || '—',
  ].join(' | ')
}

function mapApiResult(data: DirectIsbnSearchResponse): IsbnSearchResult {
  const status = (
    ['PRESENT', 'NOT FOUND', 'FOUND IN PRINTER DATA'].includes(data.status)
      ? data.status
      : data.printer
        ? 'FOUND IN PRINTER DATA'
        : 'NOT FOUND'
  ) as IsbnSearchResult['status']

  return {
    query: data.query,
    normalizedIsbn: data.normalized_isbn,
    listA: data.list_a,
    printer: data.printer,
    status,
    occurrences: data.occurrences,
    startDate: data.start_date,
    endDate: data.end_date,
    printersSearched: data.printers.map((p) => ({
      slot: p.slot,
      name: p.name,
      ok: p.ok,
      error: p.error,
    })),
  }
}

function JobDetailCard({ o }: { o: PrinterSearchOccurrence }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3.5 shadow-sm">
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Print Date
          </dt>
          <dd className="mt-0.5 text-sm font-semibold text-slate-900">
            {formatPrintDate(o.print_date)}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Job End
          </dt>
          <dd className="mt-0.5 font-mono text-sm text-slate-800">{o.job_end || '—'}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Print Start
          </dt>
          <dd className="mt-0.5 font-mono text-sm text-slate-800">{o.print_start || '—'}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Job Accept
          </dt>
          <dd className="mt-0.5 font-mono text-sm text-slate-800">{o.job_accept || '—'}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Result
          </dt>
          <dd className="mt-0.5 text-sm text-slate-800">{o.result || '—'}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Set Number
          </dt>
          <dd className="mt-0.5 text-sm text-slate-800">{o.set_number ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Output Set
          </dt>
          <dd className="mt-0.5 text-sm text-slate-800">{o.output_set ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Printer
          </dt>
          <dd className="mt-0.5 text-sm font-semibold text-slate-900">
            {shortPrinterLabel(o.printer_name, o.printer_slot)}
          </dd>
        </div>
        <div className="sm:col-span-2 lg:col-span-4">
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Source Filename
          </dt>
          <dd className="mt-0.5 break-all font-mono text-xs text-slate-700">
            {o.source_filename || '—'}
          </dd>
        </div>
      </dl>
    </div>
  )
}

type BatchRow =
  | {
      kind: 'found'
      isbn: string
      listA: boolean | null
      status: string
      occurrence: PrinterSearchOccurrence
    }
  | {
      kind: 'empty'
      isbn: string
      listA: boolean | null
      status: string
      message: string
    }

function buildBatchRows(items: DirectBatchItemResponse[]): BatchRow[] {
  const rows: BatchRow[] = []
  for (const item of items) {
    if (item.printer && item.occurrences.length > 0) {
      for (const o of item.occurrences) {
        rows.push({
          kind: 'found',
          isbn: item.normalized_isbn,
          listA: item.list_a,
          status: displayBatchStatus(item.status),
          occurrence: o,
        })
      }
    } else {
      rows.push({
        kind: 'empty',
        isbn: item.normalized_isbn,
        listA: item.list_a,
        status: displayBatchStatus(item.status),
        message:
          item.status === 'CONNECTION ISSUE'
            ? 'Printer data could not be retrieved for one or more selected printers.'
            : 'No printer record was found within the selected date range.',
      })
    }
  }
  return rows
}

function sortBatchRows(rows: BatchRow[], mode: PrintDateSort): BatchRow[] {
  return rows
    .map((row, index) => ({ row, index }))
    .sort((a, b) => {
      const aDate = a.row.kind === 'found' ? a.row.occurrence.print_date : null
      const bDate = b.row.kind === 'found' ? b.row.occurrence.print_date : null
      return compareByPrintDateSort(aDate, bDate, mode, a.index, b.index)
    })
    .map(({ row }) => row)
}

/** Build Excel rows from the same records the Search Results UI renders. */
function exportRowsFromBatch(rows: BatchRow[]): SearchResultExportRow[] {
  return rows.map((row) => {
    if (row.kind === 'found') {
      const o = row.occurrence
      return {
        isbn: row.isbn,
        list_a: listALabel(row.listA),
        printer: shortPrinterLabel(o.printer_name, o.printer_slot),
        // Same field the UI displays: occurrence.print_date
        print_date: o.print_date || '',
        job_end: o.job_end || '',
        print_start: o.print_start || '',
        job_accept: o.job_accept || '',
        result: o.result || '',
        set_number: o.set_number != null ? String(o.set_number) : '',
        output_set: o.output_set != null ? String(o.output_set) : '',
        source_filename: o.source_filename || '',
        status: row.status,
      }
    }
    return {
      isbn: row.isbn,
      list_a: listALabel(row.listA),
      printer: '',
      print_date: '',
      job_end: '',
      print_start: '',
      job_accept: '',
      result: '',
      set_number: '',
      output_set: '',
      source_filename: '',
      status: row.status,
    }
  })
}

function exportRowsFromSingle(
  result: IsbnSearchResult,
  occurrences: PrinterSearchOccurrence[],
): SearchResultExportRow[] {
  if (!result.printer || occurrences.length === 0) {
    return [
      {
        isbn: result.normalizedIsbn,
        list_a: listALabel(result.listA),
        printer: '',
        print_date: '',
        job_end: '',
        print_start: '',
        job_accept: '',
        result: '',
        set_number: '',
        output_set: '',
        source_filename: '',
        status: result.printer ? 'FOUND' : 'NOT FOUND',
      },
    ]
  }
  return occurrences.map((o) => ({
    isbn: result.normalizedIsbn,
    list_a: listALabel(result.listA),
    printer: shortPrinterLabel(o.printer_name, o.printer_slot),
    print_date: o.print_date || '',
    job_end: o.job_end || '',
    print_start: o.print_start || '',
    job_accept: o.job_accept || '',
    result: o.result || '',
    set_number: o.set_number != null ? String(o.set_number) : '',
    output_set: o.output_set != null ? String(o.output_set) : '',
    source_filename: o.source_filename || '',
    status:
      result.status === 'PRESENT' || result.status === 'FOUND IN PRINTER DATA'
        ? 'FOUND'
        : result.status,
  }))
}

type Props = {
  selectedSlots: number[]
  printerNames: Record<number, string>
  listAId: number | null
  disabled?: boolean
}

export function IsbnSearchPanel({
  selectedSlots,
  printerNames,
  listAId,
  disabled = false,
}: Props) {
  const { reportOperationFailures } = usePrinterHealth()
  const inputId = useId()
  const multiId = useId()
  const fromId = useId()
  const toId = useId()
  const sortId = useId()
  const [mode, setMode] = useState<SearchMode>('single')
  const [query, setQuery] = useState('')
  const [multiText, setMultiText] = useState('')
  const [startDate, setStartDate] = useState(daysAgoISO(90))
  const [endDate, setEndDate] = useState(todayISO())
  const [result, setResult] = useState<IsbnSearchResult | null>(null)
  const [batchResult, setBatchResult] = useState<DirectMultiIsbnSearchResponse | null>(null)
  const [batchFilter, setBatchFilter] = useState<BatchFilter>('ALL')
  const [printDateSort, setPrintDateSort] = useState<PrintDateSort>('latest')
  const [formError, setFormError] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [phase, setPhase] = useState<string | null>(null)
  const [recent, setRecent] = useState<RecentSearch[]>(() => loadRecent())
  const [copied, setCopied] = useState<string | null>(null)

  const multiParsed = useMemo(() => parseMultiIsbnInput(multiText), [multiText])
  const isbnEntered = query.trim().length > 0
  const multiEntered = multiParsed.uniqueIsbns.length > 0
  const searchEnabled =
    !searching &&
    !disabled &&
    (mode === 'single' ? isbnEntered : multiEntered)

  const selectedPrinterLabels = selectedSlots.map(
    (slot) => printerNames[slot] || `Printer ${slot}`,
  )

  const filteredBatchItems = useMemo(() => {
    if (!batchResult) return []
    if (batchFilter === 'ALL') return batchResult.results
    return batchResult.results.filter((item) => {
      const display = displayBatchStatus(item.status)
      if (batchFilter === 'FOUND') return display === 'FOUND'
      if (batchFilter === 'NOT FOUND') return display === 'NOT FOUND'
      return display === 'CONNECTION ISSUE'
    })
  }, [batchResult, batchFilter])

  const batchRows = useMemo(() => {
    const rows = buildBatchRows(filteredBatchItems)
    return sortBatchRows(rows, printDateSort)
  }, [filteredBatchItems, printDateSort])

  const sortedSingleOccurrences = useMemo(() => {
    if (!result?.occurrences?.length) return []
    return sortOccurrences(result.occurrences, printDateSort)
  }, [result, printDateSort])

  const validateDates = (from: string, to: string): string | null => {
    if (!from || !to) return 'Please select a date range.'
    if (from > to) return 'From date cannot be later than To date.'
    const today = todayISO()
    if (from > today || to > today) {
      return 'Dates cannot be in the future. Please choose today or an earlier date.'
    }
    if (!selectedSlots.length) {
      return 'Select at least one printer below (Printer & Date Range section).'
    }
    return null
  }

  const reportFailures = (
    printers: { slot: number; name: string; ok: boolean; error?: string | null }[],
  ) => {
    const failed = printers.filter((p) => !p.ok)
    if (failed.length) {
      reportOperationFailures(
        failed.map((p) => ({
          slot: p.slot,
          name: p.name || printerNames[p.slot] || `Printer ${p.slot}`,
        })),
      )
    }
  }

  const runSingleSearch = async (raw: string, from = startDate, to = endDate) => {
    setFormError(null)
    setCopied(null)
    setResult(null)
    setBatchResult(null)

    const isbn = String(raw || '').trim()
    if (!isbn) {
      setFormError('Enter an ISBN or identifier to search.')
      return
    }
    const normalized = normalizeSearchIsbn(isbn)
    if (!normalized || normalized.replace(/X/gi, '').length < 10) {
      setFormError('Enter a valid ISBN, for example 9867845312345')
      return
    }
    const dateErr = validateDates(from, to)
    if (dateErr) {
      setFormError(dateErr)
      return
    }

    setSearching(true)
    setPhase('SEARCHING PRINTERS...')
    const phaseTimer = window.setTimeout(() => {
      setPhase(
        selectedSlots.length === 1
          ? `FETCHING ${selectedPrinterLabels[0]}...`
          : `FETCHING ${selectedSlots.length} PRINTERS...`,
      )
    }, 600)
    const phaseTimer2 = window.setTimeout(() => {
      setPhase('SEARCHING PRINTER RECORDS...')
    }, 2500)

    try {
      const data = await directIsbnSearch({
        isbn,
        printer_ids: selectedSlots,
        start_date: from,
        end_date: to,
        list_a_id: listAId,
      })
      const mapped = mapApiResult(data)
      setResult(mapped)
      setQuery(mapped.normalizedIsbn)
      setStartDate(from)
      setEndDate(to)
      setRecent(
        pushRecent({
          mode: 'single',
          isbn: mapped.normalizedIsbn,
          startDate: from,
          endDate: to,
        }),
      )
      reportFailures(data.printers || [])
    } catch (err) {
      setResult(null)
      const message =
        err instanceof Error
          ? err.message
          : 'Could not retrieve printer records. Please check printer connectivity and try again.'
      setFormError(message)
      const looksLikeConnection =
        /connect|retriev|network|LAN|unreachable|unavailable|printer records/i.test(message)
      if (looksLikeConnection) {
        reportOperationFailures(
          selectedSlots.map((slot) => ({
            slot,
            name: printerNames[slot] || `Printer ${slot}`,
          })),
        )
      }
    } finally {
      window.clearTimeout(phaseTimer)
      window.clearTimeout(phaseTimer2)
      setSearching(false)
      setPhase(null)
    }
  }

  const runMultiSearch = async (rawText: string, from = startDate, to = endDate) => {
    setFormError(null)
    setCopied(null)
    setResult(null)
    setBatchResult(null)
    setBatchFilter('ALL')

    const parsed = parseMultiIsbnInput(rawText)
    if (!parsed.uniqueIsbns.length) {
      setFormError('Enter at least one valid ISBN or identifier to search.')
      return
    }
    if (parsed.uniqueIsbns.length > MAX_BATCH_ISBNS) {
      setFormError(`Please search in smaller batches. Maximum is ${MAX_BATCH_ISBNS} unique ISBNs.`)
      return
    }
    const dateErr = validateDates(from, to)
    if (dateErr) {
      setFormError(dateErr)
      return
    }

    setSearching(true)
    setPhase('SEARCHING...')
    const phaseTimer = window.setTimeout(() => {
      setPhase('Fetching printer records...')
    }, 400)
    const phaseTimer2 = window.setTimeout(() => {
      setPhase(
        selectedSlots.length === 1
          ? `Printer ${selectedSlots[0]}…`
          : `Fetching ${selectedSlots.length} printers…`,
      )
    }, 1200)
    const phaseTimer3 = window.setTimeout(() => {
      setPhase(`Searching ${parsed.uniqueIsbns.length} ISBNs...`)
    }, 2800)

    try {
      const data = await directMultiIsbnSearch({
        isbns: parsed.uniqueIsbns,
        printer_ids: selectedSlots,
        start_date: from,
        end_date: to,
        list_a_id: listAId,
        entered_count: parsed.enteredCount,
      })
      setBatchResult(data)
      setStartDate(from)
      setEndDate(to)
      setRecent(
        pushRecent({
          mode: 'multiple',
          isbn: `${data.unique_count} ISBNs`,
          multiText: rawText,
          uniqueCount: data.unique_count,
          startDate: from,
          endDate: to,
        }),
      )
      reportFailures(data.printers || [])
    } catch (err) {
      setBatchResult(null)
      const message =
        err instanceof Error
          ? err.message
          : 'Could not retrieve printer records. Please check printer connectivity and try again.'
      setFormError(message)
      const looksLikeConnection =
        /connect|retriev|network|LAN|unreachable|unavailable|printer records/i.test(message)
      if (looksLikeConnection) {
        reportOperationFailures(
          selectedSlots.map((slot) => ({
            slot,
            name: printerNames[slot] || `Printer ${slot}`,
          })),
        )
      }
    } finally {
      window.clearTimeout(phaseTimer)
      window.clearTimeout(phaseTimer2)
      window.clearTimeout(phaseTimer3)
      setSearching(false)
      setPhase(null)
    }
  }

  const clearSearch = () => {
    setQuery('')
    setMultiText('')
    setResult(null)
    setBatchResult(null)
    setBatchFilter('ALL')
    setPrintDateSort('latest')
    setFormError(null)
    setCopied(null)
    setPhase(null)
  }

  const handleCopy = async (label: string, text: string) => {
    const ok = await copyText(text)
    if (ok) {
      setCopied(label)
      window.setTimeout(() => setCopied(null), 1500)
    }
  }

  const handleExportResults = async () => {
    const rows: SearchResultExportRow[] = batchResult
      ? exportRowsFromBatch(batchRows)
      : result
        ? exportRowsFromSingle(result, sortedSingleOccurrences)
        : []
    if (!rows.length) {
      setFormError('No search results to export.')
      return
    }
    setExporting(true)
    setFormError(null)
    try {
      await exportSearchResults(rows)
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to export search results.')
    } finally {
      setExporting(false)
    }
  }

  const switchMode = (next: SearchMode) => {
    if (next === mode) return
    setMode(next)
    setResult(null)
    setBatchResult(null)
    setBatchFilter('ALL')
    setFormError(null)
    setCopied(null)
  }

  return (
    <section className="ui-card-static space-y-4 border-blue-200/70 bg-gradient-to-br from-blue-50/50 via-white to-white">
      <div>
        <div className="ui-section-label mb-1">Daily operations</div>
        <h2 className="text-base font-semibold text-slate-900">Search an ISBN</h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Search print history for any ISBN. Select a date range and click Search — printer
          records will be checked automatically. List A is not required.
        </p>
      </div>

      <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
        <button
          type="button"
          disabled={searching || disabled}
          onClick={() => switchMode('single')}
          className={
            mode === 'single'
              ? 'rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 shadow-sm'
              : 'rounded-md px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900'
          }
        >
          Single ISBN
        </button>
        <button
          type="button"
          disabled={searching || disabled}
          onClick={() => switchMode('multiple')}
          className={
            mode === 'multiple'
              ? 'rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 shadow-sm'
              : 'rounded-md px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900'
          }
        >
          Multiple ISBNs
        </button>
      </div>

      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (!searchEnabled) return
          if (mode === 'single') void runSingleSearch(query)
          else void runMultiSearch(multiText)
        }}
      >
        <div>
          <div className="text-xs font-medium text-slate-600">Date Range</div>
          <div className="mt-1 flex flex-wrap items-end gap-2">
            <label className="text-xs font-semibold text-slate-700" htmlFor={fromId}>
              From
              <input
                id={fromId}
                type="date"
                className="ui-input mt-1 block w-auto font-semibold"
                value={startDate}
                max={todayISO()}
                onChange={(e) => setStartDate(clampToToday(e.target.value))}
                disabled={searching || disabled}
              />
            </label>
            <span className="pb-2.5 text-xs font-semibold text-slate-500">to</span>
            <label className="text-xs font-semibold text-slate-700" htmlFor={toId}>
              To
              <input
                id={toId}
                type="date"
                className="ui-input mt-1 block w-auto font-semibold"
                value={endDate}
                max={todayISO()}
                onChange={(e) => setEndDate(clampToToday(e.target.value))}
                disabled={searching || disabled}
              />
            </label>
          </div>
        </div>

        {mode === 'single' ? (
          <div className="flex flex-wrap items-end gap-2">
            <label className="block min-w-[14rem] flex-1 text-xs font-medium text-slate-600" htmlFor={inputId}>
              ISBN / Identifier
              <div className="relative mt-1">
                <input
                  id={inputId}
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  spellCheck={false}
                  className="ui-input pr-10 font-mono"
                  placeholder="e.g. 9788182054370"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  disabled={searching || disabled}
                />
                {query ? (
                  <button
                    type="button"
                    aria-label="Clear input"
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:text-slate-700"
                    onClick={clearSearch}
                    disabled={searching}
                  >
                    <X size={16} />
                  </button>
                ) : (
                  <Search
                    size={16}
                    className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                    aria-hidden
                  />
                )}
              </div>
            </label>
            <button
              type="submit"
              disabled={!searchEnabled}
              className={
                searching || isbnEntered
                  ? 'ui-btn-primary font-semibold'
                  : 'ui-btn-secondary cursor-not-allowed opacity-50'
              }
            >
              {searching ? (
                <>
                  <Loader2 className="animate-spin" size={16} />
                  Searching…
                </>
              ) : (
                <>
                  <Search size={16} />
                  Search
                </>
              )}
            </button>
            <button type="button" onClick={clearSearch} className="ui-btn-secondary" disabled={searching}>
              Clear
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <label className="block text-xs font-medium text-slate-600" htmlFor={multiId}>
              Enter ISBNs / Identifiers
              <textarea
                id={multiId}
                rows={7}
                spellCheck={false}
                autoComplete="off"
                className="ui-input mt-1 block w-full resize-y font-mono text-sm leading-relaxed"
                placeholder={'9788182054370\n9789362800398\n8888001171897'}
                value={multiText}
                onChange={(e) => setMultiText(e.target.value)}
                disabled={searching || disabled}
              />
            </label>
            <p className="text-xs text-slate-500">Paste one ISBN / identifier per line.</p>
            {multiParsed.enteredCount > 0 && (
              <p className="text-xs text-slate-600">
                {multiParsed.enteredCount} ISBN{multiParsed.enteredCount === 1 ? '' : 's'} entered
                {multiParsed.uniqueIsbns.length !== multiParsed.enteredCount
                  ? ` · ${multiParsed.uniqueIsbns.length} unique`
                  : ''}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="submit"
                disabled={!searchEnabled}
                className={
                  searching || multiEntered
                    ? 'ui-btn-primary font-semibold'
                    : 'ui-btn-secondary cursor-not-allowed opacity-50'
                }
              >
                {searching ? (
                  <>
                    <Loader2 className="animate-spin" size={16} />
                    Searching…
                  </>
                ) : (
                  <>
                    <Search size={16} />
                    Search
                  </>
                )}
              </button>
              <button type="button" onClick={clearSearch} className="ui-btn-secondary" disabled={searching}>
                Clear
              </button>
            </div>
          </div>
        )}
      </form>

      <p className="text-xs text-slate-500">
        Search checks printer records for the selected date range. No List A upload is required.
        {selectedPrinterLabels.length > 0 ? (
          <>
            {' '}
            Printers to search:{' '}
            <span className="font-medium text-slate-700">{selectedPrinterLabels.join(', ')}</span>
          </>
        ) : (
          <> Select at least one printer in the section below.</>
        )}
      </p>

      {searching && (
        <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50/80 px-3 py-2.5 text-sm text-blue-950">
          <Loader2 className="animate-spin text-blue-700" size={16} />
          <span className="font-medium tracking-wide">{phase || 'SEARCHING...'}</span>
        </div>
      )}

      {recent.length > 0 && (
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Recent Searches
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {recent.map((entry) => (
              <button
                key={`${entry.mode}-${entry.isbn}-${entry.startDate}-${entry.endDate}-${entry.uniqueCount ?? ''}`}
                type="button"
                disabled={searching || disabled}
                title={`${formatPrintDate(entry.startDate)} → ${formatPrintDate(entry.endDate)}`}
                onClick={() => {
                  setStartDate(entry.startDate)
                  setEndDate(entry.endDate)
                  if (entry.mode === 'multiple') {
                    setMode('multiple')
                    const text = entry.multiText || ''
                    setMultiText(text)
                    void runMultiSearch(text, entry.startDate, entry.endDate)
                  } else {
                    setMode('single')
                    setQuery(entry.isbn)
                    void runSingleSearch(entry.isbn, entry.startDate, entry.endDate)
                  }
                }}
                className="rounded-md border border-slate-200 bg-white px-2.5 py-1 font-mono text-xs text-slate-800 shadow-sm transition-colors duration-150 hover:border-blue-300 hover:bg-blue-50 disabled:opacity-50"
              >
                {entry.mode === 'multiple'
                  ? `${entry.uniqueCount ?? '?'} ISBNs · ${formatPrintDate(entry.startDate)} → ${formatPrintDate(entry.endDate)}`
                  : entry.isbn}
              </button>
            ))}
          </div>
        </div>
      )}

      {formError && <div className="ui-alert-warn">{formError}</div>}

      {batchResult && (
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-900">
                Search Results
              </h3>
              <div className="flex flex-wrap items-center gap-2">
                <PrintDateSortControl
                  id={`${sortId}-batch`}
                  value={printDateSort}
                  onChange={setPrintDateSort}
                />
                <button
                  type="button"
                  className="ui-btn-secondary h-9 px-3 text-xs font-semibold"
                  disabled={exporting || searching || batchRows.length === 0}
                  onClick={() => void handleExportResults()}
                >
                  {exporting ? (
                    <>
                      <Loader2 className="animate-spin" size={14} />
                      Exporting…
                    </>
                  ) : (
                    <>
                      <Download size={14} />
                      Export Results
                    </>
                  )}
                </button>
              </div>
            </div>
            <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Date Range
                </dt>
                <dd className="mt-0.5 font-medium text-slate-800">
                  {formatPrintDate(batchResult.start_date)} → {formatPrintDate(batchResult.end_date)}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Printers
                </dt>
                <dd className="mt-0.5 font-medium text-slate-800">
                  {(batchResult.printers || [])
                    .map((p) =>
                      p.ok
                        ? shortPrinterLabel(p.name, p.slot)
                        : `${shortPrinterLabel(p.name, p.slot)} — DISCONNECTED`,
                    )
                    .join(', ') || '—'}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Input
                </dt>
                <dd className="mt-0.5 font-medium text-slate-800">
                  {batchResult.entered_count} ISBNs entered
                  <br />
                  {batchResult.unique_count} unique ISBNs searched
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Outcome
                </dt>
                <dd className="mt-0.5 space-y-0.5 font-medium text-slate-800">
                  <div>
                    Found: <span className="text-green-700">{batchResult.found_count}</span>
                  </div>
                  <div>
                    Not Found: <span className="text-amber-700">{batchResult.not_found_count}</span>
                  </div>
                  <div>
                    Connection Issues:{' '}
                    <span className="text-orange-700">{batchResult.connection_issue_count}</span>
                  </div>
                </dd>
              </div>
            </dl>
          </div>

          {batchResult.printers?.some((p) => !p.ok) && (
            <div className="ui-alert-warn">
              {batchResult.printers
                .filter((p) => !p.ok)
                .map((p) => (
                  <div key={p.slot}>
                    {shortPrinterLabel(p.name, p.slot)} — DISCONNECTED
                    {p.error ? `: ${p.error}` : ''}
                  </div>
                ))}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {(
              [
                ['ALL', batchResult.unique_count],
                ['FOUND', batchResult.found_count],
                ['NOT FOUND', batchResult.not_found_count],
                ['CONNECTION ISSUES', batchResult.connection_issue_count],
              ] as const
            ).map(([label, count]) => (
              <button
                key={label}
                type="button"
                onClick={() => setBatchFilter(label)}
                className={
                  batchFilter === label
                    ? 'rounded-md border border-blue-600 bg-blue-600 px-2.5 py-1 text-xs font-semibold text-white'
                    : 'rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 hover:border-blue-300'
                }
              >
                {label} {count}
              </button>
            ))}
          </div>

          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">ISBN</th>
                  <th className="px-3 py-2">List A</th>
                  <th className="px-3 py-2">Printer</th>
                  <th className="px-3 py-2">Print Date</th>
                  <th className="px-3 py-2">Job End</th>
                  <th className="px-3 py-2">Print Start</th>
                  <th className="px-3 py-2">Job Accept</th>
                  <th className="px-3 py-2">Result</th>
                  <th className="px-3 py-2">Set</th>
                  <th className="px-3 py-2">Output</th>
                  <th className="px-3 py-2">Filename</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {batchRows.length === 0 ? (
                  <tr>
                    <td colSpan={12} className="px-3 py-6 text-center text-sm text-slate-500">
                      No results in this filter.
                    </td>
                  </tr>
                ) : (
                  batchRows.map((row, idx) =>
                    row.kind === 'found' ? (
                      <tr key={`${row.isbn}-${row.occurrence.source_row}-${idx}`}>
                        <td className="px-3 py-2 font-mono text-xs font-semibold text-slate-900">
                          {row.isbn}
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-700">{listALabel(row.listA)}</td>
                        <td className="px-3 py-2 text-xs font-medium text-slate-800">
                          {shortPrinterLabel(
                            row.occurrence.printer_name,
                            row.occurrence.printer_slot,
                          )}
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-800">
                          {formatPrintDate(row.occurrence.print_date)}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-slate-800">
                          {row.occurrence.job_end || '—'}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-slate-800">
                          {row.occurrence.print_start || '—'}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-slate-800">
                          {row.occurrence.job_accept || '—'}
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-800">
                          {row.occurrence.result || '—'}
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-800">
                          {row.occurrence.set_number ?? '—'}
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-800">
                          {row.occurrence.output_set ?? '—'}
                        </td>
                        <td
                          className="max-w-[14rem] truncate px-3 py-2 font-mono text-xs text-slate-600"
                          title={row.occurrence.source_filename || undefined}
                        >
                          {row.occurrence.source_filename || '—'}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-semibold ${statusClasses(row.status)}`}
                          >
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    ) : (
                      <tr key={`${row.isbn}-empty-${idx}`} className="bg-amber-50/40">
                        <td className="px-3 py-2 font-mono text-xs font-semibold text-slate-900">
                          {row.isbn}
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-700">{listALabel(row.listA)}</td>
                        <td className="px-3 py-2 text-xs text-slate-400">—</td>
                        <td className="px-3 py-2 text-xs text-slate-400">—</td>
                        <td className="px-3 py-2 text-xs text-slate-400">—</td>
                        <td className="px-3 py-2 text-xs text-slate-400">—</td>
                        <td className="px-3 py-2 text-xs text-slate-400">—</td>
                        <td className="px-3 py-2 text-xs text-slate-400">—</td>
                        <td className="px-3 py-2 text-xs text-slate-400">—</td>
                        <td className="px-3 py-2 text-xs text-slate-400">—</td>
                        <td className="px-3 py-2 text-xs text-slate-500" title={row.message}>
                          {row.message}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-semibold ${statusClasses(row.status)}`}
                          >
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    ),
                  )
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result && (
        <div
          className={`rounded-xl border p-4 ${
            result.printer
              ? 'border-green-200 bg-gradient-to-br from-green-50/80 to-white'
              : 'border-amber-200 bg-gradient-to-br from-amber-50/60 to-white'
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              {result.printer ? (
                <CheckCircle2 size={18} className="text-green-600" aria-hidden />
              ) : (
                <XCircle size={18} className="text-amber-600" aria-hidden />
              )}
              {resultTitle(result)}
            </h3>
            <div className="flex flex-wrap items-center gap-2">
              {result.printer && result.occurrences.length > 0 && (
                <PrintDateSortControl
                  id={`${sortId}-single`}
                  value={printDateSort}
                  onChange={setPrintDateSort}
                />
              )}
              <button
                type="button"
                className="ui-btn-secondary h-9 px-3 text-xs font-semibold"
                disabled={exporting || searching}
                onClick={() => void handleExportResults()}
              >
                {exporting ? (
                  <>
                    <Loader2 className="animate-spin" size={14} />
                    Exporting…
                  </>
                ) : (
                  <>
                    <Download size={14} />
                    Export Results
                  </>
                )}
              </button>
              <span
                className={`inline-flex rounded-md border px-2.5 py-0.5 text-xs font-semibold ${statusClasses(result.status)}`}
              >
                {result.status}
              </span>
            </div>
          </div>

          <p className="mt-2 text-xs text-slate-500">
            Search range:{' '}
            <span className="font-medium text-slate-700">
              {formatPrintDate(result.startDate)} → {formatPrintDate(result.endDate)}
            </span>
            {result.printersSearched && result.printersSearched.length > 0 && (
              <>
                <br />
                Printers searched:{' '}
                <span className="font-medium text-slate-700">
                  {result.printersSearched
                    .map((p) =>
                      p.ok
                        ? shortPrinterLabel(p.name, p.slot)
                        : `${shortPrinterLabel(p.name, p.slot)} — DISCONNECTED`,
                    )
                    .join(', ')}
                </span>
              </>
            )}
          </p>

          {result.printersSearched?.some((p) => !p.ok) && (
            <div className="ui-alert-warn mt-3">
              {result.printersSearched
                .filter((p) => !p.ok)
                .map((p) => (
                  <div key={p.slot}>
                    {shortPrinterLabel(p.name, p.slot)} — DISCONNECTED
                    {p.error ? `: ${p.error}` : ''}
                  </div>
                ))}
            </div>
          )}

          <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                ISBN
              </dt>
              <dd className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-sm font-semibold text-slate-900">
                {result.normalizedIsbn}
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-xs font-sans font-medium text-slate-700 hover:bg-slate-50"
                  onClick={() => void handleCopy('isbn', result.normalizedIsbn)}
                >
                  <Copy size={12} />
                  {copied === 'isbn' ? 'Copied' : 'Copy'}
                </button>
              </dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                List A
              </dt>
              <dd className="mt-0.5 text-sm font-semibold text-slate-900">
                {listALabel(result.listA)}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Printer
              </dt>
              <dd className="mt-0.5 text-sm font-semibold text-slate-900">
                {result.printer ? 'YES' : 'NO'}
              </dd>
            </div>
            {result.printer && sortedSingleOccurrences[0] && (
              <div>
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Printed
                </dt>
                <dd className="mt-0.5 text-sm font-semibold text-slate-900">
                  {formatPrintDate(sortedSingleOccurrences[0].print_date)}
                </dd>
              </div>
            )}
          </dl>

          {result.printer && sortedSingleOccurrences.length > 0 && (
            <div className="mt-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Print History
                  <span className="ml-1.5 font-normal normal-case text-slate-400">
                    ({sortedSingleOccurrences.length}{' '}
                    {sortedSingleOccurrences.length === 1 ? 'job' : 'jobs'})
                  </span>
                </h4>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-xs text-slate-700 hover:bg-slate-50"
                  onClick={() =>
                    void handleCopy(
                      'details',
                      [
                        `ISBN: ${result.normalizedIsbn}`,
                        `List A: ${listALabel(result.listA)}`,
                        `Printer: YES`,
                        `Status: ${result.status}`,
                        `Search range: ${formatPrintDate(result.startDate)} → ${formatPrintDate(result.endDate)}`,
                        '',
                        'Print History:',
                        ...sortedSingleOccurrences.map(formatOccurrenceLine),
                      ].join('\n'),
                    )
                  }
                >
                  <Copy size={12} />
                  {copied === 'details' ? 'Copied' : 'Copy Print Details'}
                </button>
              </div>

              <div className="mt-2 space-y-2">
                {sortedSingleOccurrences.map((o, i) => (
                  <JobDetailCard
                    key={`${o.source_row ?? i}-${o.printer_slot}-${o.print_date ?? i}-${i}`}
                    o={o}
                  />
                ))}
              </div>
            </div>
          )}

          {!result.printer && (
            <p className="mt-3 text-sm text-slate-600">
              No printer record for this ISBN was found within the selected date range.
            </p>
          )}
        </div>
      )}

      {!result && !batchResult && !formError && !searching && (
        <div className="rounded-lg border border-dashed border-slate-200 bg-white/70 px-4 py-5 text-center">
          <p className="text-sm font-medium text-slate-800">Ready to search</p>
          <p className="mt-1 text-sm text-slate-500">
            {mode === 'single'
              ? 'Enter an ISBN, choose a date range, and click Search. Printer records are fetched automatically — no prior reconciliation required.'
              : 'Paste ISBNs (one per line), choose a date range, and click Search. Printer data is fetched once per selected printer for the whole batch.'}
          </p>
        </div>
      )}
    </section>
  )
}
