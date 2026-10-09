import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { AppLayout } from '../components/AppLayout'
import { updateNetworkPrinter } from '../services/api'
import { usePrinterHealth } from '../lib/printerHealth'

export function PrinterConfigPage() {
  const {
    printers,
    live,
    loadingConfigs,
    configError,
    refreshConfigs,
    reloadPrinterNames,
    checkSlot,
    reportOperationFailures,
  } = usePrinterHealth()

  const [error, setError] = useState<string | null>(null)
  const [savingSlot, setSavingSlot] = useState<number | null>(null)
  const [draftNames, setDraftNames] = useState<Record<number, string>>({})
  const seededRef = useRef(false)

  useEffect(() => {
    if (printers.length && !seededRef.current) {
      setDraftNames(Object.fromEntries(printers.map((p) => [p.slot, p.name])))
      seededRef.current = true
    } else if (printers.length) {
      setDraftNames((prev) => {
        const next = { ...prev }
        for (const p of printers) {
          if (next[p.slot] == null) next[p.slot] = p.name
        }
        return next
      })
    }
  }, [printers])

  useEffect(() => {
    if (configError) setError(configError)
  }, [configError])

  const handleTest = async (slot: number) => {
    const ok = await checkSlot(slot)
    if (!ok) {
      const name = printers.find((p) => p.slot === slot)?.name || `Printer ${slot}`
      reportOperationFailures([{ slot, name }])
    }
  }

  const handleSaveName = useCallback(
    async (slot: number) => {
      const name = (draftNames[slot] || '').trim()
      if (!name) return
      setSavingSlot(slot)
      try {
        await updateNetworkPrinter(slot, { name })
        await reloadPrinterNames()
      } catch {
        setError('Could not save printer name.')
      } finally {
        setSavingSlot(null)
      }
    },
    [draftNames, reloadPrinterNames],
  )

  return (
    <AppLayout>
      <main className="ui-page">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="ui-section-label mb-1">Configuration</div>
            <h1 className="ui-page-title">Connect to Printer</h1>
            <p className="ui-page-subtitle">
              Status reflects the latest live reachability check (auto-refreshed about every 30
              seconds). Passwords stay on the server and are never shown in the browser.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refreshConfigs()}
            className="ui-btn-secondary"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>

        {error && <div className="ui-alert-error">{error}</div>}

        <div className="ui-alert-warn">
          <div className="font-medium">Admin / IT only</div>
          <div className="mt-1">
            Printer passwords are configured on the server. If a connection fails, ask IT to
            confirm the computer is on the printer network and that printer credentials are set.
          </div>
        </div>

        {loadingConfigs && printers.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="animate-spin text-blue-700" size={16} />
            Loading printer configuration…
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            {printers.map((printer) => {
              const status = live[printer.slot]
              const phase = status?.phase ?? 'checking'
              const statusMsg =
                status?.result?.message ?? status?.error ?? printer.last_connection_message
              const checkedAt = status?.checkedAt ?? status?.result?.checked_at

              return (
                <div key={printer.slot} className="ui-card-static flex flex-col">
                  <div className="mb-3 flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Printer {printer.slot}
                      </div>
                      <input
                        className="ui-input mt-1 font-semibold"
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
                      className={`shrink-0 rounded-md border px-2 py-0.5 text-xs font-medium ${
                        printer.protocol === 'https'
                          ? 'border-blue-200 bg-blue-50 text-blue-800'
                          : 'border-slate-200 bg-slate-50 text-slate-700'
                      }`}
                    >
                      {printer.protocol.toUpperCase()}
                    </span>
                  </div>

                  <div className="mb-1 flex items-center gap-2 text-sm">
                    {phase === 'checking' ? (
                      <>
                        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-sky-500" />
                        <span className="font-medium text-sky-800">Checking…</span>
                      </>
                    ) : phase === 'connected' ? (
                      <>
                        <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                        <span className="font-medium text-green-800">Connected</span>
                      </>
                    ) : (
                      <>
                        <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
                        <span className="font-medium text-red-800">Disconnected</span>
                      </>
                    )}
                  </div>

                  <p className="mb-3 min-h-[2.5rem] text-xs text-slate-500">
                    {phase === 'checking'
                      ? 'Live reachability check in progress…'
                      : statusMsg ||
                        (phase === 'connected'
                          ? 'Printer responded successfully.'
                          : 'Unable to reach the printer.')}
                  </p>

                  <div className="mt-auto space-y-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
                    <div>
                      Endpoint:{' '}
                      <span className="font-mono text-slate-700">{printer.display_endpoint}</span>
                    </div>
                    <div>Last checked: {checkedAt ? new Date(checkedAt).toLocaleTimeString() : '—'}</div>
                    <button
                      type="button"
                      className="ui-btn-primary w-full"
                      onClick={() => handleTest(printer.slot)}
                      disabled={phase === 'checking'}
                    >
                      {phase === 'checking' ? (
                        <>
                          <Loader2 className="animate-spin" size={16} />
                          Checking…
                        </>
                      ) : (
                        'Test Connection'
                      )}
                    </button>
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
