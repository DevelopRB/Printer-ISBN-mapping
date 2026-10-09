import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, Download, Loader2, XCircle } from 'lucide-react'
import { AppLayout } from '../components/AppLayout'
import { IsbnSearchPanel } from '../components/IsbnSearchPanel'
import {
  automatedNormalizedExportUrl,
  getAutomatedRun,
  listAutomatedRuns,
  listListAUploads,
  retryFailedPrinters,
  startAutomatedRun,
  uploadListAForAutomation,
} from '../services/api'
import { usePrinterHealth } from '../lib/printerHealth'
import type {
  AutomatedRun,
  ListAUploadInfo,
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
  const {
    printers,
    systemStatus,
    checkSlots,
    reportOperationFailures,
  } = usePrinterHealth()

  const [listAOptions, setListAOptions] = useState<ListAUploadInfo[]>([])
  const [selectedListAId, setSelectedListAId] = useState<number | null>(null)
  const [selectedSlots, setSelectedSlots] = useState<number[]>([])
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
  const notifiedRunFailuresRef = useRef<Set<number>>(new Set())
  const didInitSlotsRef = useRef(false)

  // Default: search/reconcile across all configured printers (not Printer 1 only).
  useEffect(() => {
    if (!printers.length || didInitSlotsRef.current) return
    setSelectedSlots(printers.map((p) => p.slot).sort((a, b) => a - b))
    didInitSlotsRef.current = true
  }, [printers])

  const selectedListA = useMemo(
    () => listAOptions.find((x) => x.id === selectedListAId) || null,
    [listAOptions, selectedListAId],
  )

  const refreshMeta = useCallback(async () => {
    const [la, runs] = await Promise.all([listListAUploads(), listAutomatedRuns()])
    setListAOptions(la)
    setHistory(runs)
    // Do not auto-select a List A — user must choose or upload deliberately.
    return runs
  }, [])

  useEffect(() => {
    void (async () => {
      try {
        const runs = await refreshMeta()
        // Restore latest completed run for export / progress history after refresh.
        const latestDone = runs.find((r) =>
          ['COMPLETED', 'PARTIAL_SUCCESS'].includes(r.status),
        )
        if (latestDone) {
          const full = await getAutomatedRun(latestDone.id)
          setRun(full)
        }
      } catch {
        setError('Could not load automation data. Is the backend running?')
      }
    })()
    // intentionally once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const stopPoll = () => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const notifyFailedDownloads = (latest: AutomatedRun) => {
    if (notifiedRunFailuresRef.current.has(latest.id)) return
    const failed = (latest.downloads || [])
      .filter((d) => String(d.status).toUpperCase() === 'FAILED')
      .map((d) => ({
        slot: d.printer_slot,
        name: d.printer_name || `Printer ${d.printer_slot}`,
      }))
    if (!failed.length) return
    notifiedRunFailuresRef.current.add(latest.id)
    reportOperationFailures(failed)
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
          notifyFailedDownloads(latest)
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

    // Fresh reachability check before starting download/reconcile.
    setBusy(true)
    try {
      const reachability = await checkSlots(selectedSlots)
      const unreachable = reachability.filter((r) => !r.ok)
      if (unreachable.length) {
        setBusy(false)
        reportOperationFailures(unreachable.map((r) => ({ slot: r.slot, name: r.name })))
        return
      }
    } catch {
      setBusy(false)
      setError('Could not verify printer connectivity. Please try again.')
      return
    }

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

  const systemBadge = (() => {
    if (running) {
      return {
        label: 'Processing…',
        dot: 'bg-blue-500',
        wrap: 'border-blue-200 bg-blue-50 text-blue-900',
      }
    }
    if (systemStatus === 'checking') {
      return {
        label: 'Checking',
        dot: 'animate-pulse bg-sky-500',
        wrap: 'border-sky-200 bg-sky-50 text-sky-900',
      }
    }
    if (systemStatus === 'ready') {
      return {
        label: 'System Ready',
        dot: 'bg-green-500',
        wrap: 'border-green-200 bg-green-50 text-green-900',
      }
    }
    if (systemStatus === 'unknown') {
      return {
        label: 'Check Connection',
        dot: 'bg-amber-500',
        wrap: 'border-amber-200 bg-amber-50 text-amber-950',
      }
    }
    return {
      label: 'Connection Issue',
      dot: 'bg-red-500',
      wrap: 'border-red-200 bg-red-50 text-red-900',
    }
  })()

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
            className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3">
              <CheckCircle2 className="mt-0.5 shrink-0 text-green-600" size={22} />
              <div>
                <h2 id="export-ready-title" className="text-lg font-semibold text-slate-900">
                  {run.list_a_upload_id
                    ? 'Ready to export your file'
                    : 'Printer data ready'}
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  {run.list_a_upload_id
                    ? `Reconciliation is complete${
                        run.status === 'PARTIAL_SUCCESS' ? ' (some printers had issues)' : ''
                      }. You can download the reports now.`
                    : `Printer download finished${
                        run.status === 'PARTIAL_SUCCESS' ? ' (some printers had issues)' : ''
                      }. You can export the printer report now. Direct ISBN Search does not need this run — it fetches printer data on its own.`}
                </p>
              </div>
            </div>
            <div className="mt-5 flex flex-col gap-2">
              <a
                href={automatedNormalizedExportUrl(run.id)}
                className="ui-btn-primary w-full"
                onClick={() => setExportReadyOpen(false)}
              >
                <Download size={16} />
                Export Normalized Report
              </a>
            </div>
            <button
              type="button"
              className="mt-4 w-full rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
              onClick={() => setExportReadyOpen(false)}
            >
              Close
            </button>
          </div>
        </div>
      )}

      <main className="ui-page">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="ui-section-label mb-1">Primary workflow</div>
            <h1 className="ui-page-title">Automated Reconciliation</h1>
            <p className="ui-page-subtitle">
              Search any ISBN with a date range (printer data is fetched automatically), or run a
              full reconciliation with optional List A and Excel export. Manual Reconciliation
              remains available as an emergency / fallback option.
            </p>
          </div>
          <div
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${systemBadge.wrap}`}
          >
            <span className={`inline-block h-2 w-2 rounded-full ${systemBadge.dot}`} aria-hidden />
            {systemBadge.label}
          </div>
        </header>

        <IsbnSearchPanel
          selectedSlots={selectedSlots}
          printerNames={Object.fromEntries(printers.map((p) => [p.slot, p.name]))}
          listAId={selectedListAId}
          disabled={!!running}
        />

        {error && <div className="ui-alert-error">{error}</div>}

        <section className="ui-card-static space-y-6">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <span className="ui-step-badge">1</span>
              <div>
                <h2 className="text-sm font-semibold text-slate-900">
                  Upload List A <span className="font-normal text-slate-500">(optional)</span>
                </h2>
                <p className="mt-0.5 text-xs text-slate-500">
                  (books that were given to the printer for printing)
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Needed for reconciliation reports. Skip this step if you only want to download
                  printer data and search ISBNs.
                </p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <label className="block text-xs font-medium text-slate-600">
                Existing List A
                <select
                  className="ui-input mt-1 block w-72"
                  value={selectedListAId ?? ''}
                  onChange={(e) =>
                    setSelectedListAId(e.target.value ? Number(e.target.value) : null)
                  }
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
                className="ui-btn-secondary"
              >
                {uploading ? (
                  <>
                    <Loader2 className="animate-spin" size={16} />
                    Uploading…
                  </>
                ) : (
                  'Upload New List A'
                )}
              </button>
            </div>
            {selectedListA && (
              <div className="ui-alert-success mt-3">
                <div className="font-medium">{selectedListA.filename}</div>
                <div className="mt-0.5 text-green-800/80">
                  Records: {selectedListA.record_count.toLocaleString('en-IN')} · Unique ISBNs
                  detected: {selectedListA.isbn_detected_count.toLocaleString('en-IN')} · Uploaded:{' '}
                  {new Date(selectedListA.uploaded_at).toLocaleString()}
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-slate-100 pt-5">
            <div className="mb-3 flex items-center gap-2">
              <span className="ui-step-badge">2</span>
              <h2 className="text-sm font-semibold text-slate-900">Printer &amp; Date Range</h2>
            </div>
            <div className="mt-3 flex flex-wrap gap-3">
              {printers.map((p) => (
                <label
                  key={p.slot}
                  className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors duration-150 ${
                    selectedSlots.includes(p.slot)
                      ? 'border-blue-300 bg-blue-50 text-blue-950'
                      : 'border-slate-200 bg-white text-slate-800 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    className="accent-blue-700"
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
              className="mt-2 text-xs font-medium text-blue-800 underline-offset-2 hover:underline"
              disabled={!!running}
              onClick={() => setSelectedSlots(printers.map((p) => p.slot))}
            >
              Select All Printers
            </button>

            <div className="mt-4 flex flex-wrap gap-4">
              <label className="text-xs font-medium text-slate-600">
                From Date
                <input
                  type="date"
                  className="ui-input mt-1 block w-auto"
                  value={startDate}
                  max={todayISO()}
                  onChange={(e) => setStartDate(clampToToday(e.target.value))}
                  disabled={!!running}
                />
              </label>
              <label className="text-xs font-medium text-slate-600">
                To Date
                <input
                  type="date"
                  className="ui-input mt-1 block w-auto"
                  value={endDate}
                  max={todayISO()}
                  onChange={(e) => setEndDate(clampToToday(e.target.value))}
                  disabled={!!running}
                />
              </label>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-5">
            <div className="mb-3 flex items-center gap-2">
              <span className="ui-step-badge">3</span>
              <h2 className="text-sm font-semibold text-slate-900">Download &amp; Reconcile</h2>
            </div>
            <button
              type="button"
              disabled={!!running}
              onClick={() => void handleStart()}
              className="ui-btn-primary"
            >
              {running ? <Loader2 className="animate-spin" size={16} /> : null}
              {running ? 'Fetching Printer Data…' : 'Download Printer Data & Reconcile'}
            </button>
          </div>
        </section>

        {run && (
          <section className="ui-card-static space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="ui-section-label">Progress</div>
                <h2 className="mt-0.5 text-sm font-semibold text-slate-900">
                  Run #{run.id} · {run.status}
                  {!run.list_a_upload_id &&
                  ['COMPLETED', 'PARTIAL_SUCCESS'].includes(run.status)
                    ? ' · Printer data ready'
                    : ''}
                </h2>
                {!run.list_a_upload_id &&
                  ['COMPLETED', 'PARTIAL_SUCCESS'].includes(run.status) && (
                    <p className="mt-1 text-xs text-slate-500">
                      No List A was uploaded — this run finished printer download and ISBN search
                      only. Upload List A if you need a full reconciliation report.
                    </p>
                  )}
              </div>
              {run.status === 'PARTIAL_SUCCESS' && (
                <button
                  type="button"
                  className="ui-btn-secondary border-amber-300 bg-amber-50 text-amber-950 hover:bg-amber-100"
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
            <ol className="space-y-2 text-sm">
              {run.steps.map((step) => (
                <li key={step.key} className="flex items-start gap-2.5">
                  <StepIcon status={step.status} />
                  <div>
                    <div className="font-medium text-slate-800">{step.label}</div>
                    {step.detail && <div className="text-xs text-slate-500">{step.detail}</div>}
                  </div>
                </li>
              ))}
            </ol>
            {run.downloads.length > 0 && (
              <div className="space-y-3 border-t border-slate-100 pt-4">
                <div className="text-sm font-semibold text-slate-800">Download Printer Data</div>
                {run.downloads.map((d) => {
                  const ok =
                    ['COMPLETED', 'SUCCESS', 'SUCCESSFUL', 'EMPTY'].includes(d.status.toUpperCase()) &&
                    !d.error_message
                  const failed = d.status.toUpperCase() === 'FAILED' || !!d.error_message
                  return (
                    <div
                      key={d.id}
                      className={`rounded-xl border px-4 py-3.5 text-sm ${
                        failed
                          ? 'border-red-200 bg-red-50/40'
                          : ok
                            ? 'border-blue-200/80 bg-gradient-to-br from-blue-50/80 to-white'
                            : 'border-slate-200 bg-slate-50'
                      }`}
                    >
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <div className="text-base font-semibold text-slate-900">{d.printer_name}</div>
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
                            failed
                              ? 'border-red-200 bg-red-50 text-red-800'
                              : ok
                                ? 'border-green-200 bg-green-50 text-green-800'
                                : 'border-sky-200 bg-sky-50 text-sky-800'
                          }`}
                        >
                          <span
                            className={`inline-block h-1.5 w-1.5 rounded-full ${
                              failed ? 'bg-red-500' : ok ? 'bg-green-500' : 'bg-sky-500'
                            }`}
                            aria-hidden
                          />
                          {downloadStatusLabel(d.status)}
                        </span>
                      </div>
                      {d.error_message && (
                        <p className="mb-3 text-sm text-red-800">{d.error_message}</p>
                      )}
                      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        <div>
                          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                            Report Date Range
                          </dt>
                          <dd className="mt-0.5 font-medium text-slate-900">
                            {formatReportDate(d.start_date)} → {formatReportDate(d.end_date)}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                            Downloaded On
                          </dt>
                          <dd className="mt-0.5 font-medium text-slate-900">
                            {formatDownloadedOn(d.retrieved_at)}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                            Records Retrieved
                          </dt>
                          <dd className="mt-0.5 font-medium tabular-nums text-slate-900">
                            {d.record_count != null ? d.record_count.toLocaleString('en-IN') : '—'}
                          </dd>
                        </div>
                        {run.summary && (
                          <>
                            <div>
                              <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                ISBN Records
                              </dt>
                              <dd className="mt-0.5 font-medium tabular-nums text-slate-900">
                                {(
                                  (run.summary.valid_isbns ?? run.summary.printer_isbns) || 0
                                ).toLocaleString('en-IN')}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                Skipped Records
                              </dt>
                              <dd className="mt-0.5 font-medium tabular-nums text-slate-900">
                                {(run.summary.printer_without_isbn || 0).toLocaleString('en-IN')}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                                ISBNs Processed
                              </dt>
                              <dd className="mt-0.5 font-medium tabular-nums text-slate-900">
                                {(
                                  (run.summary.valid_isbns ?? run.summary.printer_isbns) || 0
                                ).toLocaleString('en-IN')}
                              </dd>
                            </div>
                          </>
                        )}
                      </dl>
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        )}

        {run && summary && ['COMPLETED', 'PARTIAL_SUCCESS'].includes(run.status) && (
          <section className="ui-card-static space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="ui-section-label">Results</div>
                <h2 className="mt-0.5 text-base font-semibold text-slate-900">
                  {run.list_a_upload_id
                    ? 'Printing Reconciliation'
                    : 'Printer Data Results'}
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Report Date Range: {formatReportDate(run.start_date)} →{' '}
                  {formatReportDate(run.end_date)} · Printers:{' '}
                  {run.printer_slots
                    .map((s) => printers.find((p) => p.slot === s)?.name || `Printer ${s}`)
                    .join(', ')}
                  {!run.list_a_upload_id
                    ? ' · No List A (search / printer export only)'
                    : ''}
                </p>
              </div>
              <a href={automatedNormalizedExportUrl(run.id)} className="ui-btn-primary">
                <Download size={16} />
                Export Normalized Report
              </a>
            </div>
            <div className="space-y-5">
              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  List A Reconciliation
                </h3>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
                  <Card label="List A ISBNs" value={summary.unique_isbns} tone="neutral" />
                  <Card
                    label="Found"
                    value={summary.found ?? summary.matched ?? 0}
                    tone="success"
                  />
                  <Card
                    label="Not Found"
                    value={summary.not_found ?? summary.not_reported ?? 0}
                    tone="danger"
                  />
                  <Card label="Duplicate List A" value={summary.duplicates ?? 0} tone="warn" />
                  <Card label="Needs Review" value={summary.needs_review ?? 0} tone="warn" />
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
                    tone="info"
                  />
                  <Card
                    label="Not in List A"
                    value={summary.printer_not_in_list_a ?? summary.unexpected ?? 0}
                    tone="info"
                  />
                  <Card
                    label="Identifier Not Extracted"
                    value={summary.printer_without_isbn ?? 0}
                    tone="neutral"
                  />
                </div>
              </div>
            </div>
          </section>
        )}

        <section className="ui-card-static">
          <h2 className="ui-section-label mb-3">Reconciliation History</h2>
          {history.length === 0 ? (
            <p className="text-sm text-slate-500">No previous runs yet.</p>
          ) : (
            <div className="flex flex-wrap items-end gap-3">
              <label className="block min-w-[20rem] flex-1 text-xs font-medium text-slate-600">
                Previous run
                <select
                  className="ui-input mt-1"
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
  tone = 'neutral',
}: {
  label: string
  value: number
  tone?: 'neutral' | 'success' | 'danger' | 'warn' | 'info'
}) {
  const toneClass =
    tone === 'success'
      ? 'ui-stat-success'
      : tone === 'danger'
        ? 'ui-stat-danger'
        : tone === 'warn'
          ? 'ui-stat-warn'
          : tone === 'info'
            ? 'ui-stat-info'
            : ''
  return (
    <div className={`ui-stat ${toneClass}`}>
      <div className="ui-stat-label">{label}</div>
      <div className="ui-stat-value text-xl">{value.toLocaleString('en-IN')}</div>
    </div>
  )
}
