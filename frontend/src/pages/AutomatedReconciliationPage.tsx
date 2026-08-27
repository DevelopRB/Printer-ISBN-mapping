import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, Download, Loader2, XCircle } from 'lucide-react'
import { AppLayout } from '../components/AppLayout'
import {
  automatedNormalizedExportUrl,
  getAutomatedRun,
  listAutomatedRuns,
  listListAUploads,
  listNetworkPrinters,
  retryFailedPrinters,
  startAutomatedRun,
  uploadListAForAutomation,
} from '../services/api'
import type {
  AutomatedRun,
  ListAUploadInfo,
  NetworkPrinterConfig,
} from '../types'

/** Local calendar date as YYYY-MM-DD (not UTC — avoids off-by-one near midnight). */
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

/** Display date as 01-Aug-2026 from ISO YYYY-MM-DD or Date. */
function formatReportDate(value: string | Date | null | undefined): string {
  if (!value) return '—'
  const d = typeof value === 'string' ? new Date(value.length === 10 ? `${value}T00:00:00` : value) : value
  if (Number.isNaN(d.getTime())) return String(value)
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const dd = String(d.getDate()).padStart(2, '0')
  return `${dd}-${months[d.getMonth()]}-${d.getFullYear()}`
}

/** Display download timestamp as 27-Aug-2026 11:20 AM */
function formatDownloadedOn(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const dd = String(d.getDate()).padStart(2, '0')
  let hours = d.getHours()
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const ampm = hours >= 12 ? 'PM' : 'AM'
  hours = hours % 12 || 12
  return `${dd}-${months[d.getMonth()]}-${d.getFullYear()} ${hours}:${minutes} ${ampm}`
}

function downloadStatusLabel(status: string): string {
  const s = status.toUpperCase()
  if (s === 'COMPLETED' || s === 'SUCCESS' || s === 'SUCCESSFUL') return 'Successful'
  if (s === 'EMPTY') return 'No records found'
  if (s === 'FAILED') return 'Failed'
  if (s === 'PENDING' || s === 'RUNNING') return 'In progress'
  return status
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
  const [uploading, setUploading] = useState(false)
  const [exportReadyOpen, setExportReadyOpen] = useState(false)
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
          const runs = await listAutomatedRuns()
          setHistory(runs)
          if (['COMPLETED', 'PARTIAL_SUCCESS'].includes(latest.status)) {
            setExportReadyOpen(true)
          }
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
    const today = todayISO()
    if (startDate > today || endDate > today) {
      setError('Dates cannot be in the future. Please choose today or an earlier date.')
      return
    }
    if (startDate > endDate) {
      setError('From date must be on or before To date.')
      return
    }
    setBusy(true)
    setExportReadyOpen(false)
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
      {exportReadyOpen && run && ['COMPLETED', 'PARTIAL_SUCCESS'].includes(run.status) && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="export-ready-title"
          onClick={() => setExportReadyOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3">
              <CheckCircle2 className="mt-0.5 shrink-0 text-green-600" size={22} />
              <div>
                <h2 id="export-ready-title" className="text-lg font-semibold text-slate-900">
                  Ready to export your file
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  Reconciliation is complete
                  {run.status === 'PARTIAL_SUCCESS' ? ' (some printers had issues)' : ''}.
                  You can download the reports now.
                </p>
              </div>
            </div>
            <div className="mt-5 flex flex-col gap-2">
              <a
                href={automatedNormalizedExportUrl(run.id)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-slate-800 bg-slate-800 px-3 py-2.5 text-sm font-medium text-white hover:bg-slate-700"
                onClick={() => setExportReadyOpen(false)}
              >
                <Download size={16} />
                Export Normalized Report
              </a>
            </div>
            <button
              type="button"
              className="mt-4 w-full rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
              onClick={() => setExportReadyOpen(false)}
            >
              Close
            </button>
          </div>
        </div>
      )}

      <main className="mx-auto max-w-[1400px] space-y-6 px-4 py-6 sm:px-6">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">
            Reconcile
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Connect to a printer, download printer data for a report date range, and match ISBNs
            against List A. Manual Excel upload remains available on the Manual Reconciliation page.
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
            <h2 className="text-sm font-semibold text-slate-800">Step 2 — Connect to Printer</h2>
            <div className="mt-3 flex flex-wrap gap-4">
              {printers.map((p) => (
                <label key={p.slot} className="inline-flex items-center gap-2 text-sm text-slate-800">
                  <input
                    type="checkbox"
                    checked={selectedSlots.includes(p.slot)}
                    onChange={() => toggleSlot(p.slot)}
                    disabled={!!running}
                  />
                  {p.name}
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
            <h2 className="text-sm font-semibold text-slate-800">Step 3 — Report Date Range</h2>
            <div className="mt-3 flex flex-wrap gap-4">
              <label className="text-xs text-slate-600">
                From Date
                <input
                  type="date"
                  className="mt-1 block rounded-md border border-slate-300 px-2 py-2 text-sm"
                  value={startDate}
                  max={todayISO()}
                  onChange={(e) => setStartDate(clampToToday(e.target.value))}
                  disabled={!!running}
                />
              </label>
              <label className="text-xs text-slate-600">
                To Date
                <input
                  type="date"
                  className="mt-1 block rounded-md border border-slate-300 px-2 py-2 text-sm"
                  value={endDate}
                  max={todayISO()}
                  onChange={(e) => setEndDate(clampToToday(e.target.value))}
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
            Download Printer Data &amp; Reconcile
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
              <div className="space-y-3 border-t border-slate-100 pt-3">
                <div className="font-medium text-slate-700">Download Printer Data</div>
                {run.downloads.map((d) => (
                  <div
                    key={d.id}
                    className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm"
                  >
                    <dl className="grid gap-2 sm:grid-cols-2">
                      <div>
                        <dt className="text-xs uppercase tracking-wide text-slate-500">Printer</dt>
                        <dd className="font-medium text-slate-900">{d.printer_name}</dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-wide text-slate-500">
                          Download Status
                        </dt>
                        <dd className="font-medium text-slate-900">
                          {downloadStatusLabel(d.status)}
                          {d.error_message ? ` — ${d.error_message}` : ''}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-wide text-slate-500">
                          Report Date Range
                        </dt>
                        <dd className="font-medium text-slate-900">
                          {formatReportDate(d.start_date)} → {formatReportDate(d.end_date)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-wide text-slate-500">
                          Downloaded On
                        </dt>
                        <dd className="font-medium text-slate-900">
                          {formatDownloadedOn(d.retrieved_at)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-wide text-slate-500">
                          Records Retrieved
                        </dt>
                        <dd className="font-medium tabular-nums text-slate-900">
                          {d.record_count != null ? d.record_count.toLocaleString('en-IN') : '—'}
                        </dd>
                      </div>
                      {run.summary && (
                        <>
                          <div>
                            <dt className="text-xs uppercase tracking-wide text-slate-500">
                              ISBN Records
                            </dt>
                            <dd className="font-medium tabular-nums text-slate-900">
                              {(
                                (run.summary.valid_isbns ?? run.summary.printer_isbns) || 0
                              ).toLocaleString('en-IN')}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-wide text-slate-500">
                              Skipped Records
                            </dt>
                            <dd className="font-medium tabular-nums text-slate-900">
                              {(run.summary.printer_without_isbn || 0).toLocaleString('en-IN')}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-wide text-slate-500">
                              ISBNs Processed
                            </dt>
                            <dd className="font-medium tabular-nums text-slate-900">
                              {(
                                (run.summary.valid_isbns ?? run.summary.printer_isbns) || 0
                              ).toLocaleString('en-IN')}
                            </dd>
                          </div>
                        </>
                      )}
                    </dl>
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
                    Report Date Range: {formatReportDate(run.start_date)} →{' '}
                    {formatReportDate(run.end_date)} · Printers:{' '}
                    {run.printer_slots
                      .map((s) => printers.find((p) => p.slot === s)?.name || `Printer ${s}`)
                      .join(', ')}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
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
                    <Card label="Found" value={summary.found ?? summary.matched ?? 0} />
                    <Card label="Not Found" value={summary.not_found ?? summary.not_reported ?? 0} />
                    <Card label="Duplicate List A" value={summary.duplicates ?? 0} />
                    <Card label="Needs Review" value={summary.needs_review ?? 0} />
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
                    />
                    <Card
                      label="Identifier Not Extracted"
                      value={summary.printer_without_isbn ?? 0}
                    />
                  </div>
                </div>
              </div>
            </section>
          </>
        )}

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">
            Reconciliation History
          </h2>
          {history.length === 0 ? (
            <p className="text-sm text-slate-500">No previous runs yet.</p>
          ) : (
            <div className="flex flex-wrap items-end gap-3">
              <label className="block min-w-[20rem] flex-1 text-xs text-slate-600">
                Previous run
                <select
                  className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-2 text-sm text-slate-900"
                  value={run?.id ?? ''}
                  disabled={!!running}
                  onChange={(e) => {
                    const id = Number(e.target.value)
                    if (!id) return
                    void (async () => {
                      try {
                        const full = await getAutomatedRun(id)
                        setRun(full)
                        setError(null)
                      } catch {
                        setError('Could not open that run.')
                      }
                    })()
                  }}
                >
                  <option value="">Select a previous run…</option>
                  {history.map((h) => {
                    const printersLabel = h.printer_slots
                      .map((s) => printers.find((p) => p.slot === s)?.name || `Printer ${s}`)
                      .join(', ')
                    const found = h.summary?.found ?? h.summary?.matched ?? 0
                    const notFound = h.summary?.not_found ?? h.summary?.not_reported ?? 0
                    const range = `${formatReportDate(h.start_date)} → ${formatReportDate(h.end_date)}`
                    return (
                      <option key={h.id} value={h.id}>
                        #{h.id} · {h.status} · {range} · {printersLabel}
                        {h.summary ? ` · ${found} found · ${notFound} not found` : ''}
                        {h.list_a_filename ? ` · ${h.list_a_filename}` : ''}
                      </option>
                    )
                  })}
                </select>
              </label>
            </div>
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
}: {
  label: string
  value: number
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-left shadow-sm">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums text-slate-900">
        {value.toLocaleString('en-IN')}
      </div>
    </div>
  )
}
