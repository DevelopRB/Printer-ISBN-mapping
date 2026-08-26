import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, Download, Loader2, XCircle } from 'lucide-react'
import { AppLayout } from '../components/AppLayout'
import { StatusBadge } from '../components/StatusBadge'
import {
  automatedExportUrl,
  automatedNormalizedExportUrl,
  getAutomatedPrinterRecords,
  getAutomatedResults,
  getAutomatedRun,
  listAutomatedRuns,
  listListAUploads,
  listNetworkPrinters,
  retryFailedPrinters,
  startAutomatedRun,
  uploadListAForAutomation,
} from '../services/api'
import type {
  AutomatedResultRow,
  AutomatedRun,
  ListAUploadInfo,
  NetworkPrinterConfig,
} from '../types'

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function daysAgoISO(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

export function AutomatedReconciliationPage() {
  const [listAOptions, setListAOptions] = useState<ListAUploadInfo[]>([])
  const [selectedListAId, setSelectedListAId] = useState<number | null>(null)
  const [printers, setPrinters] = useState<NetworkPrinterConfig[]>([])
  const [selectedSlots, setSelectedSlots] = useState<number[]>([1])
  const [startDate, setStartDate] = useState(daysAgoISO(7))
  const [endDate, setEndDate] = useState(todayISO())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [run, setRun] = useState<AutomatedRun | null>(null)
  const [history, setHistory] = useState<AutomatedRun[]>([])
  const [rows, setRows] = useState<AutomatedResultRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [view, setView] = useState<'results' | 'printer'>('results')
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<number | null>(null)

  const selectedListA = useMemo(
    () => listAOptions.find((x) => x.id === selectedListAId) || null,
    [listAOptions, selectedListAId],
  )

  const refreshMeta = useCallback(async () => {
    const [la, pr, runs] = await Promise.all([
      listListAUploads(),
      listNetworkPrinters(),
      listAutomatedRuns(),
    ])
    setListAOptions(la)
    setPrinters(pr)
    setHistory(runs)
    if (!selectedListAId && la[0]) setSelectedListAId(la[0].id)
  }, [selectedListAId])

  useEffect(() => {
    void refreshMeta().catch(() => setError('Could not load automation data. Is the backend running?'))
  }, [refreshMeta])

  const loadResults = useCallback(
    async (runId: number, p = 1, status?: string, mode: 'results' | 'printer' = 'results') => {
      if (mode === 'printer') {
        const res = await getAutomatedPrinterRecords(runId, { page: p, page_size: 50 })
        setRows(res.items)
        setTotal(res.total)
      } else {
        const res = await getAutomatedResults(runId, {
          page: p,
          page_size: 50,
          status,
        })
        setRows(res.items)
        setTotal(res.total)
      }
      setPage(p)
    },
    [],
  )

  const stopPoll = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const startPoll = (runId: number) => {
    stopPoll()
    pollRef.current = window.setInterval(async () => {
      try {
        const latest = await getAutomatedRun(runId)
        setRun(latest)
        if (['COMPLETED', 'PARTIAL_SUCCESS', 'FAILED'].includes(latest.status)) {
          stopPoll()
          setBusy(false)
          await loadResults(runId, 1, statusFilter, view)
          const runs = await listAutomatedRuns()
          setHistory(runs)
        }
      } catch {
        /* keep polling briefly */
      }
    }, 1500)
  }

  useEffect(() => () => stopPoll(), [])

  const toggleSlot = (slot: number) => {
    setSelectedSlots((prev) =>
      prev.includes(slot) ? prev.filter((s) => s !== slot) : [...prev, slot].sort(),
    )
  }

  const handleStart = async () => {
    setError(null)
    if (!selectedListAId) {
      setError('Select or upload a List A file.')
      return
    }
    if (!selectedSlots.length) {
      setError('Select at least one printer.')
      return
    }
    if (startDate > endDate) {
      setError('From date must be on or before To date.')
      return
    }
    setBusy(true)
    setRows([])
    setTotal(0)
    setStatusFilter(undefined)
    setView('results')
    try {
      const started = await startAutomatedRun({
        list_a_id: selectedListAId,
        printer_ids: selectedSlots,
        start_date: startDate,
        end_date: endDate,
      })
      setRun(started)
      startPoll(started.id)
    } catch (err) {
      setBusy(false)
      setError(err instanceof Error ? err.message : 'Failed to start run.')
    }
  }

  const handleUpload = async (file: File) => {
    setUploading(true)
    setError(null)
    try {
      const uploaded = await uploadListAForAutomation(file)
      await refreshMeta()
      setSelectedListAId(uploaded.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const summary = run?.summary
  const running = busy || (run && ['PENDING', 'RUNNING'].includes(run.status))

  return (
    <AppLayout>
      <main className="mx-auto max-w-[1400px] space-y-6 px-4 py-6 sm:px-6">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">
            Automated Reconciliation
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Fetch printer job logs for a date range and match ISBNs against List A. Manual Excel
            upload remains available on the Reconciliation page.
          </p>
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </div>
        )}

        <section className="space-y-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Step 1 — Select List A</h2>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <label className="block text-xs text-slate-600">
                Existing List A
                <select
                  className="mt-1 block w-72 rounded-md border border-slate-300 px-2 py-2 text-sm"
                  value={selectedListAId ?? ''}
                  onChange={(e) => setSelectedListAId(Number(e.target.value))}
                >
                  <option value="">Select…</option>
                  {listAOptions.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.filename} ({u.record_count} rows)
                    </option>
                  ))}
                </select>
              </label>
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  e.target.value = ''
                  if (f) void handleUpload(f)
                }}
              />
              <button
                type="button"
                disabled={uploading || !!running}
                onClick={() => fileRef.current?.click()}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
              >
                {uploading ? 'Uploading…' : 'Upload New List A'}
              </button>
            </div>
            {selectedListA && (
              <div className="mt-3 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900">
                <div className="font-medium">{selectedListA.filename}</div>
                <div>
                  Records: {selectedListA.record_count.toLocaleString('en-IN')} · Unique ISBNs
                  detected: {selectedListA.isbn_detected_count.toLocaleString('en-IN')} · Uploaded:{' '}
                  {new Date(selectedListA.uploaded_at).toLocaleString()}
                </div>
              </div>
            )}
          </div>

          <div>
            <h2 className="text-sm font-semibold text-slate-800">Step 2 — Select Printer</h2>
            <div className="mt-3 flex flex-wrap gap-4">
              {printers.map((p) => (
                <label key={p.slot} className="inline-flex items-center gap-2 text-sm text-slate-800">
                  <input
                    type="checkbox"
                    checked={selectedSlots.includes(p.slot)}
                    onChange={() => toggleSlot(p.slot)}
                    disabled={!!running}
                  />
                  {p.name} ({p.display_endpoint})
                </label>
              ))}
            </div>
            <button
              type="button"
              className="mt-2 text-xs text-sky-800 underline"
              disabled={!!running}
              onClick={() => setSelectedSlots(printers.map((p) => p.slot))}
            >
              Select All Printers
            </button>
          </div>

          <div>
            <h2 className="text-sm font-semibold text-slate-800">Step 3 — Date Range</h2>
            <div className="mt-3 flex flex-wrap gap-4">
              <label className="text-xs text-slate-600">
                From Date
                <input
                  type="date"
                  className="mt-1 block rounded-md border border-slate-300 px-2 py-2 text-sm"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  disabled={!!running}
                />
              </label>
              <label className="text-xs text-slate-600">
                To Date
                <input
                  type="date"
                  className="mt-1 block rounded-md border border-slate-300 px-2 py-2 text-sm"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  disabled={!!running}
                />
              </label>
            </div>
          </div>

          <button
            type="button"
            disabled={!!running}
            onClick={() => void handleStart()}
            className="inline-flex items-center gap-2 rounded-md bg-slate-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {running ? <Loader2 className="animate-spin" size={16} /> : null}
            Fetch &amp; Reconcile
          </button>
        </section>

        {run && (
          <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                Progress · Run #{run.id} · {run.status}
              </h2>
              {run.status === 'PARTIAL_SUCCESS' && (
                <button
                  type="button"
                  className="rounded-md border border-amber-300 bg-amber-50 px-3 py-1.5 text-sm text-amber-900"
                  onClick={async () => {
                    setBusy(true)
                    const next = await retryFailedPrinters(run.id)
                    setRun(next)
                    startPoll(next.id)
                  }}
                >
                  Retry Failed Printers
                </button>
              )}
            </div>
            <ol className="space-y-1.5 text-sm">
              {run.steps.map((step) => (
                <li key={step.key} className="flex items-start gap-2">
                  <StepIcon status={step.status} />
                  <div>
                    <div className="text-slate-800">{step.label}</div>
                    {step.detail && <div className="text-xs text-slate-500">{step.detail}</div>}
                  </div>
                </li>
              ))}
            </ol>
            {run.downloads.length > 0 && (
              <div className="border-t border-slate-100 pt-3 text-sm">
                <div className="mb-1 font-medium text-slate-700">Downloads</div>
                {run.downloads.map((d) => (
                  <div key={d.id} className="text-slate-600">
                    {d.printer_name}: {d.status}
                    {d.record_count != null ? ` · ${d.record_count.toLocaleString('en-IN')} jobs` : ''}
                    {d.error_message ? ` · ${d.error_message}` : ''}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {run && summary && ['COMPLETED', 'PARTIAL_SUCCESS'].includes(run.status) && (
          <>
            <section className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                    Printing Reconciliation
                  </h2>
                  <p className="text-sm text-slate-500">
                    Date Range: {run.start_date} → {run.end_date} · Printers:{' '}
                    {run.printer_slots.map((s) => printers.find((p) => p.slot === s)?.name || `Printer ${s}`).join(', ')}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <a
                    href={automatedExportUrl(run.id)}
                    className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50"
                  >
                    <Download size={16} />
                    Export Detailed Report
                  </a>
                  <a
                    href={automatedNormalizedExportUrl(run.id)}
                    className="inline-flex items-center gap-2 rounded-md border border-slate-800 bg-slate-800 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700"
                  >
                    <Download size={16} />
                    Export Normalized Report
                  </a>
                </div>
              </div>
              <div className="space-y-5">
                <div>
                  <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    List A Reconciliation
                  </h3>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
                    <Card label="List A ISBNs" value={summary.unique_isbns} />
                    <Card
                      label="Found"
                      value={summary.found ?? summary.matched ?? 0}
                      active={statusFilter === 'FOUND'}
                      onClick={() => {
                        const next = statusFilter === 'FOUND' ? undefined : 'FOUND'
                        setStatusFilter(next)
                        setView('results')
                        void loadResults(run.id, 1, next, 'results')
                      }}
                    />
                    <Card
                      label="Not Found"
                      value={summary.not_found ?? summary.not_reported ?? 0}
                      active={statusFilter === 'NOT_FOUND'}
                      onClick={() => {
                        const next = statusFilter === 'NOT_FOUND' ? undefined : 'NOT_FOUND'
                        setStatusFilter(next)
                        setView('results')
                        void loadResults(run.id, 1, next, 'results')
                      }}
                    />
                    <Card
                      label="Duplicate List A"
                      value={summary.duplicates ?? 0}
                      active={statusFilter === 'DUPLICATE_IN_LIST_A'}
                      onClick={() => {
                        const next =
                          statusFilter === 'DUPLICATE_IN_LIST_A' ? undefined : 'DUPLICATE_IN_LIST_A'
                        setStatusFilter(next)
                        setView('results')
                        void loadResults(run.id, 1, next, 'results')
                      }}
                    />
                    <Card
                      label="Needs Review"
                      value={summary.needs_review ?? 0}
                      active={statusFilter === 'NEEDS_REVIEW'}
                      onClick={() => {
                        const next = statusFilter === 'NEEDS_REVIEW' ? undefined : 'NEEDS_REVIEW'
                        setStatusFilter(next)
                        setView('results')
                        void loadResults(run.id, 1, next, 'results')
                      }}
                    />
                  </div>
                </div>
                <div>
                  <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Printer Audit
                  </h3>
                  <p className="mb-3 text-xs text-slate-500">
                    Not mixed into List A counts — additional printer ISBNs or unreadable filenames.
                  </p>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                    <Card
                      label="Printer ISBNs"
                      value={summary.printer_isbns ?? summary.valid_isbns ?? 0}
                    />
                    <Card
                      label="Not in List A"
                      value={summary.printer_not_in_list_a ?? summary.unexpected ?? 0}
                      active={statusFilter === 'PRINTER_RECORDS_NOT_IN_LIST_A'}
                      onClick={() => {
                        const next =
                          statusFilter === 'PRINTER_RECORDS_NOT_IN_LIST_A'
                            ? undefined
                            : 'PRINTER_RECORDS_NOT_IN_LIST_A'
                        setStatusFilter(next)
                        setView('results')
                        void loadResults(run.id, 1, next, 'results')
                      }}
                    />
                    <Card
                      label="Identifier Not Extracted"
                      value={summary.printer_without_isbn ?? 0}
                      active={statusFilter === 'ISBN_NOT_FOUND'}
                      onClick={() => {
                        const next =
                          statusFilter === 'ISBN_NOT_FOUND' ? undefined : 'ISBN_NOT_FOUND'
                        setStatusFilter(next)
                        setView('results')
                        void loadResults(run.id, 1, next, 'results')
                      }}
                    />
                  </div>
                </div>
              </div>
            </section>

            <div className="flex gap-2 text-sm">
              <button
                type="button"
                className={`rounded-md px-3 py-1.5 ${view === 'results' ? 'bg-slate-800 text-white' : 'border border-slate-300'}`}
                onClick={() => {
                  setView('results')
                  void loadResults(run.id, 1, statusFilter, 'results')
                }}
              >
                Reconciliation
              </button>
              <button
                type="button"
                className={`rounded-md px-3 py-1.5 ${view === 'printer' ? 'bg-slate-800 text-white' : 'border border-slate-300'}`}
                onClick={() => {
                  setView('printer')
                  setStatusFilter(undefined)
                  void loadResults(run.id, 1, undefined, 'printer')
                }}
              >
                Printer Raw Records
              </button>
            </div>

            <ResultsTable rows={rows} />
            <Pagination
              page={page}
              total={total}
              pageSize={50}
              onChange={(p) => void loadResults(run.id, p, statusFilter, view)}
            />
          </>
        )}

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">
            Reconciliation History
          </h2>
          {history.length === 0 ? (
            <p className="text-sm text-slate-500">No automated runs yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {history.map((h) => (
                <li key={h.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <div>
                    <div className="font-medium text-slate-800">
                      #{h.id} · {h.status} · {h.start_date} → {h.end_date}
                    </div>
                    <div className="text-slate-500">
                      {h.list_a_filename} · Printers {h.printer_slots.join(', ')} ·{' '}
                      {h.summary
                        ? `${h.summary.found ?? h.summary.matched ?? 0} found · ${h.summary.not_found ?? h.summary.not_reported ?? 0} not found`
                        : '—'}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
                    onClick={async () => {
                      const full = await getAutomatedRun(h.id)
                      setRun(full)
                      if (['COMPLETED', 'PARTIAL_SUCCESS'].includes(full.status)) {
                        await loadResults(full.id, 1, undefined, 'results')
                      }
                    }}
                  >
                    Open
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </AppLayout>
  )
}

function StepIcon({ status }: { status: string }) {
  if (status === 'done') return <CheckCircle2 className="mt-0.5 text-green-600" size={16} />
  if (status === 'running') return <Loader2 className="mt-0.5 animate-spin text-sky-700" size={16} />
  if (status === 'error') return <XCircle className="mt-0.5 text-red-600" size={16} />
  return <span className="mt-1 inline-block h-3 w-3 rounded-full border border-slate-300" />
}

function Card({
  label,
  value,
  active,
  onClick,
}: {
  label: string
  value: number
  active?: boolean
  onClick?: () => void
}) {
  const clickable = Boolean(onClick)
  return (
    <button
      type="button"
      disabled={!clickable}
      onClick={onClick}
      className={`rounded-lg border border-slate-200 bg-white p-3 text-left shadow-sm ${
        clickable ? 'hover:border-slate-300 cursor-pointer' : 'cursor-default'
      } ${active ? 'ring-2 ring-slate-400' : ''}`}
    >
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums text-slate-900">
        {value.toLocaleString('en-IN')}
      </div>
    </button>
  )
}

function ResultsTable({ rows }: { rows: AutomatedResultRow[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
            <tr>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3">ISBN</th>
              <th className="px-3 py-3">Item</th>
              <th className="px-3 py-3">Party</th>
              <th className="px-3 py-3">Voucher No.</th>
              <th className="px-3 py-3">List A Date</th>
              <th className="px-3 py-3">Pending Qty</th>
              <th className="px-3 py-3">Printer</th>
              <th className="px-3 py-3">Printer Date</th>
              <th className="px-3 py-3">Printer Occurrences</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr>
                <td colSpan={10} className="px-3 py-8 text-center text-slate-500">
                  No rows.
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-slate-50/80">
                <td className="px-3 py-2">
                  <StatusBadge status={row.status} />
                </td>
                <td className="px-3 py-2 font-mono text-xs">{row.isbn || '—'}</td>
                <td className="px-3 py-2 max-w-[200px] truncate">{row.item || '—'}</td>
                <td className="px-3 py-2 max-w-[160px] truncate">{row.party || '—'}</td>
                <td className="px-3 py-2">{row.voucher_no || '—'}</td>
                <td className="px-3 py-2 whitespace-nowrap">{row.list_a_date || '—'}</td>
                <td className="px-3 py-2">{row.pending_qty || '—'}</td>
                <td className="px-3 py-2">
                  {row.printer_names.length ? row.printer_names.join(', ') : '—'}
                </td>
                <td className="px-3 py-2">
                  {row.printer_dates.filter(Boolean).join(', ') || '—'}
                </td>
                <td className="px-3 py-2 tabular-nums">
                  {row.printer_occurrences ??
                    (row.original_printer_values?.length
                      ? row.original_printer_values.filter(Boolean).length
                      : 0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Pagination({
  page,
  total,
  pageSize,
  onChange,
}: {
  page: number
  total: number
  pageSize: number
  onChange: (p: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="flex items-center justify-between text-sm text-slate-600">
      <span>
        {(page - 1) * pageSize + (total ? 1 : 0)}–{Math.min(page * pageSize, total)} of{' '}
        {total.toLocaleString('en-IN')}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={page <= 1}
          className="rounded border border-slate-300 px-3 py-1 disabled:opacity-40"
          onClick={() => onChange(page - 1)}
        >
          Previous
        </button>
        <span className="px-2 py-1">
          Page {page} / {pages}
        </span>
        <button
          type="button"
          disabled={page >= pages}
          className="rounded border border-slate-300 px-3 py-1 disabled:opacity-40"
          onClick={() => onChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  )
}
