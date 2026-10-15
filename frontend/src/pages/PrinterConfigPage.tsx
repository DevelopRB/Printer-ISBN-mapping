import { useCallback, useEffect, useRef, useState } from 'react'
import { Eye, EyeOff, KeyRound, Loader2, RefreshCw } from 'lucide-react'
import { AppLayout } from '../components/AppLayout'
import { savePrinterCredentials, updateNetworkPrinter } from '../services/api'
import { usePrinterHealth } from '../lib/printerHealth'
import type { NetworkPrinterConfig } from '../types'

function PrinterLoginForm({
  printer,
  disabled,
  onSaved,
}: {
  printer: NetworkPrinterConfig
  disabled: boolean
  onSaved: () => Promise<void>
}) {
  const [username, setUsername] = useState(printer.username || 'admin')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    if (printer.username) setUsername(printer.username)
  }, [printer.username])

  const hasSavedPassword = printer.password_configured
  const canSave = !!username.trim() && (hasSavedPassword || !!password) && !saving && !disabled

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSave) return
    setSaving(true)
    setMessage(null)
    try {
      await savePrinterCredentials(printer.slot, {
        username: username.trim(),
        ...(password ? { password } : {}),
      })
      setPassword('')
      setShowPassword(false)
      setMessage({ ok: true, text: 'Saved on this computer. Checking connection…' })
      await onSaved()
      setMessage({ ok: true, text: 'Saved on this computer.' })
    } catch (err) {
      setMessage({
        ok: false,
        text: err instanceof Error ? err.message : 'Could not save the printer login.',
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSave} className="space-y-2 rounded-lg border border-slate-200 p-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 font-semibold text-slate-700">
          <KeyRound size={13} aria-hidden />
          Printer login
        </span>
        <span
          className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
            hasSavedPassword ? 'bg-green-50 text-green-800' : 'bg-amber-50 text-amber-800'
          }`}
        >
          {hasSavedPassword ? 'Password saved' : 'Password not set'}
        </span>
      </div>
      <label className="block">
        Username
        <input
          className="ui-input mt-1 h-9 py-1.5 text-xs text-slate-800"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
          disabled={saving}
        />
      </label>
      <label className="block">
        Password
        <div className="relative mt-1">
          <input
            className="ui-input h-9 py-1.5 pr-9 text-xs text-slate-800"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={hasSavedPassword ? 'Leave blank to keep saved password' : 'Enter printer password'}
            autoComplete="new-password"
            disabled={saving}
          />
          <button
            type="button"
            className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-slate-400 hover:text-slate-700"
            onClick={() => setShowPassword((v) => !v)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            tabIndex={-1}
          >
            {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
      </label>
      <button type="submit" className="ui-btn-secondary w-full" disabled={!canSave}>
        {saving ? (
          <>
            <Loader2 className="animate-spin" size={14} />
            Saving…
          </>
        ) : (
          'Save login'
        )}
      </button>
      {message && (
        <div className={message.ok ? 'text-green-700' : 'text-red-700'}>{message.text}</div>
      )}
    </form>
  )
}

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

  const handleSelectEndpoint = useCallback(
    async (slot: number, protocol: string, port: number) => {
      setSavingSlot(slot)
      setError(null)
      try {
        await updateNetworkPrinter(slot, { protocol, port })
        await refreshConfigs()
      } catch {
        setError('Could not change the printer connection address.')
      } finally {
        setSavingSlot(null)
      }
    },
    [refreshConfigs],
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
              seconds). Printer passwords are saved only on this computer and are never shown
              again.
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
          <div className="font-medium">First-time setup on this computer</div>
          <div className="mt-1">
            Enter the username and password for each printer under <b>Printer login</b> and
            click <b>Save login</b>. You only need to do this once — they are used automatically
            every time the app starts and are kept when the app updates. If a printer still
            won&apos;t connect, check that this computer is on the printer network.
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
                    {printer.endpoint_options && printer.endpoint_options.length > 1 ? (
                      <label className="block">
                        Connect using:
                        <select
                          className="ui-input mt-1 h-9 py-1.5 font-mono text-xs text-slate-800"
                          value={`${printer.protocol}:${printer.port}`}
                          disabled={savingSlot === printer.slot || phase === 'checking'}
                          onChange={(e) => {
                            const opt = printer.endpoint_options?.find(
                              (o) => `${o.protocol}:${o.port}` === e.target.value,
                            )
                            if (opt) void handleSelectEndpoint(printer.slot, opt.protocol, opt.port)
                          }}
                        >
                          {printer.endpoint_options.map((o) => (
                            <option key={`${o.protocol}:${o.port}`} value={`${o.protocol}:${o.port}`}>
                              {o.display_endpoint} ({o.protocol.toUpperCase()})
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : (
                      <div>
                        Endpoint:{' '}
                        <span className="font-mono text-slate-700">{printer.display_endpoint}</span>
                      </div>
                    )}
                    <div>Last checked: {checkedAt ? new Date(checkedAt).toLocaleTimeString() : '—'}</div>
                    <PrinterLoginForm
                      printer={printer}
                      disabled={savingSlot === printer.slot}
                      onSaved={async () => {
                        await reloadPrinterNames()
                        await checkSlot(printer.slot)
                      }}
                    />
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
