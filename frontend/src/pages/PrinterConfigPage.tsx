import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Loader2, RefreshCw, XCircle } from 'lucide-react'
import { AppLayout } from '../components/AppLayout'
import {
  listNetworkPrinters,
  testNetworkPrinterConnection,
  updateNetworkPrinter,
} from '../services/api'
import type { ConnectionTestResult, NetworkPrinterConfig } from '../types'

type TestState = {
  loading?: boolean
  result?: ConnectionTestResult
  error?: string
}

export function PrinterConfigPage() {
  const [printers, setPrinters] = useState<NetworkPrinterConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tests, setTests] = useState<Record<number, TestState>>({})
  const [savingSlot, setSavingSlot] = useState<number | null>(null)
  const [draftNames, setDraftNames] = useState<Record<number, string>>({})

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await listNetworkPrinters()
      setPrinters(rows)
      setDraftNames(Object.fromEntries(rows.map((p) => [p.slot, p.name])))
    } catch {
      setError('Could not load printer configuration. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const handleTest = async (slot: number) => {
    setTests((prev) => ({ ...prev, [slot]: { loading: true } }))
    try {
      const result = await testNetworkPrinterConnection(slot)
      setTests((prev) => ({ ...prev, [slot]: { loading: false, result } }))
      setPrinters((prev) =>
        prev.map((p) =>
          p.slot === slot
            ? {
                ...p,
                last_connection_ok: result.ok,
                last_connection_category: result.category,
                last_connection_message: result.message,
                last_connection_http_status: result.http_status,
                last_connection_latency_ms: result.latency_ms,
                last_checked_at: result.checked_at,
                password_configured: result.password_configured,
              }
            : p,
        ),
      )
    } catch (err) {
      setTests((prev) => ({
        ...prev,
        [slot]: {
          loading: false,
          error: err instanceof Error ? err.message : 'Connection test failed.',
        },
      }))
    }
  }

  const handleSaveName = async (slot: number) => {
    const name = (draftNames[slot] || '').trim()
    if (!name) return
    setSavingSlot(slot)
    try {
      const updated = await updateNetworkPrinter(slot, { name })
      setPrinters((prev) => prev.map((p) => (p.slot === slot ? updated : p)))
    } catch {
      setError('Could not save printer name.')
    } finally {
      setSavingSlot(null)
    }
  }

  return (
    <AppLayout>
      <main className="mx-auto max-w-[1400px] space-y-6 px-4 py-6 sm:px-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">
              Printer Configuration
            </h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-500">
              Network endpoints for job-log retrieval. Passwords are read from server environment
              variables only and are never sent to the browser. Job-log download is not enabled yet
              — connection testing only (Phase 2A/2B).
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </div>
        )}

        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Set <code className="font-mono text-xs">PRINTER_n_PASSWORD</code> in the project{' '}
          <code className="font-mono text-xs">.env</code> file on the backend host. HTTPS printers
          use <code className="font-mono text-xs">PRINTER_VERIFY_SSL</code> (default false for
          internal self-signed certificates — MitM risk on untrusted networks).
        </div>

        {loading ? (
          <p className="text-slate-500">Loading printer configuration…</p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            {printers.map((printer) => {
              const test = tests[printer.slot]
              const statusOk = test?.result?.ok ?? printer.last_connection_ok
              const statusMsg =
                test?.result?.message ??
                test?.error ??
                printer.last_connection_message
              const checkedAt = test?.result?.checked_at ?? printer.last_checked_at

              return (
                <div
                  key={printer.slot}
                  className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
                >
                  <div className="mb-3 flex items-start justify-between gap-2">
                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                        Printer {printer.slot}
                      </div>
                      <input
                        className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm font-semibold text-slate-900"
                        value={draftNames[printer.slot] ?? printer.name}
                        onChange={(e) =>
                          setDraftNames((prev) => ({
                            ...prev,
                            [printer.slot]: e.target.value,
                          }))
                        }
                        onBlur={() => void handleSaveName(printer.slot)}
                        disabled={savingSlot === printer.slot}
                      />
                    </div>
                    <span
                      className={`rounded border px-2 py-0.5 text-xs font-medium ${
                        printer.protocol === 'https'
                          ? 'border-sky-200 bg-sky-50 text-sky-800'
                          : 'border-slate-200 bg-slate-50 text-slate-700'
                      }`}
                    >
                      {printer.protocol.toUpperCase()}
                    </span>
                  </div>

                  <dl className="space-y-2 text-sm">
                    <Row label="Endpoint" value={printer.display_endpoint} mono />
                    <Row label="Base URL" value={printer.base_url} mono />
                    <Row label="Job log path" value={printer.joblog_path} mono />
                    <Row
                      label="Username env"
                      value={`${printer.username_env}${printer.username_configured ? ' ✓' : ' (default admin)'}`}
                    />
                    <Row
                      label="Password env"
                      value={`${printer.password_env}${printer.password_configured ? ' ✓ set' : ' ✕ missing'}`}
                    />
                    {printer.protocol === 'https' && (
                      <Row
                        label="SSL verify"
                        value={printer.verify_ssl ? 'enabled' : 'disabled (internal)'}
                      />
                    )}
                  </dl>

                  <div className="mt-4 border-t border-slate-100 pt-4">
                    <button
                      type="button"
                      disabled={!!test?.loading}
                      onClick={() => void handleTest(printer.slot)}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-slate-800 px-3 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                    >
                      {test?.loading ? (
                        <>
                          <Loader2 className="animate-spin" size={16} />
                          Testing…
                        </>
                      ) : (
                        'Test Connection'
                      )}
                    </button>

                    <div className="mt-3 min-h-[3.5rem]">
                      {statusOk === true && (
                        <StatusLine
                          ok
                          message={statusMsg || 'Connected'}
                          meta={formatMeta(test?.result ?? null, checkedAt, printer)}
                        />
                      )}
                      {statusOk === false && (
                        <StatusLine
                          ok={false}
                          message={statusMsg || 'Connection failed'}
                          meta={formatMeta(test?.result ?? null, checkedAt, printer)}
                        />
                      )}
                      {statusOk == null && !test?.loading && !test?.error && (
                        <p className="text-sm text-slate-500">Not tested yet.</p>
                      )}
                      {test?.error && statusOk == null && (
                        <StatusLine ok={false} message={test.error} meta="" />
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>
    </AppLayout>
  )
}

function Row({
  label,
  value,
  mono,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd
        className={`text-right text-slate-900 break-all ${mono ? 'font-mono text-xs' : ''}`}
      >
        {value}
      </dd>
    </div>
  )
}

function StatusLine({
  ok,
  message,
  meta,
}: {
  ok: boolean
  message: string
  meta: string
}) {
  return (
    <div
      className={`rounded-md border px-3 py-2 text-sm ${
        ok
          ? 'border-green-200 bg-green-50 text-green-900'
          : 'border-red-200 bg-red-50 text-red-900'
      }`}
    >
      <div className="flex items-start gap-2 font-medium">
        {ok ? (
          <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
        ) : (
          <XCircle size={16} className="mt-0.5 shrink-0" />
        )}
        <span>{ok ? 'Connected' : message}</span>
      </div>
      {(meta || (ok && message && message !== 'Connected')) && (
        <div className="mt-0.5 pl-6 text-xs opacity-90">
          {ok && message && message !== 'Connected' ? <div>{message}</div> : null}
          {meta ? <div>{meta}</div> : null}
        </div>
      )}
    </div>
  )
}

function formatMeta(
  result: ConnectionTestResult | null,
  checkedAt: string | null | undefined,
  printer: NetworkPrinterConfig,
): string {
  const parts: string[] = []
  const latency = result?.latency_ms ?? printer.last_connection_latency_ms
  const http = result?.http_status ?? printer.last_connection_http_status
  if (latency != null) parts.push(`${latency} ms`)
  if (http != null) parts.push(`HTTP ${http}`)
  if (checkedAt) {
    try {
      parts.push(new Date(checkedAt).toLocaleString())
    } catch {
      parts.push(checkedAt)
    }
  }
  return parts.join(' · ')
}
