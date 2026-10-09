import { Loader2, WifiOff, CheckCircle2, XCircle } from 'lucide-react'
import type { ConnectionModalState } from '../lib/printerHealth'

type Props = {
  state: ConnectionModalState | null
  onClose: () => void
  onTest: () => void
}

export function ConnectionIssueModal({ state, onClose, onTest }: Props) {
  if (!state) return null

  const multi = state.printers.length > 1
  const names = state.printers.map((p) => p.name)

  let title = 'NO CONNECTION'
  if (state.phase === 'checking') title = 'CHECKING...'
  else if (state.phase === 'restored') title = 'CONNECTION RESTORED'
  else if (state.phase === 'failed') title = 'CONNECTION FAILED'
  else if (multi) title = 'PRINTER CONNECTION ISSUE'

  const testLabel = multi ? 'Test Connections' : 'Test Connection'

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="connection-issue-title"
      onClick={() => {
        if (state.phase !== 'checking') onClose()
      }}
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          {state.phase === 'restored' ? (
            <CheckCircle2 className="mt-0.5 shrink-0 text-green-600" size={22} />
          ) : state.phase === 'checking' ? (
            <Loader2 className="mt-0.5 shrink-0 animate-spin text-blue-700" size={22} />
          ) : (
            <WifiOff className="mt-0.5 shrink-0 text-red-600" size={22} aria-hidden />
          )}
          <div className="min-w-0 flex-1">
            <h2
              id="connection-issue-title"
              className={`text-lg font-semibold tracking-wide ${
                state.phase === 'restored'
                  ? 'text-green-900'
                  : state.phase === 'checking'
                    ? 'text-blue-950'
                    : 'text-red-900'
              }`}
            >
              {title}
            </h2>

            {state.phase === 'issue' && !multi && (
              <div className="mt-2 space-y-2 text-sm text-slate-600">
                <p className="font-medium text-slate-800">
                  {state.detail || `${names[0]} could not be reached.`}
                </p>
                <p>Please check:</p>
                <ul className="list-disc space-y-0.5 pl-5 text-slate-700">
                  <li>Printer power</li>
                  <li>LAN cable</li>
                  <li>Network connection</li>
                </ul>
              </div>
            )}

            {state.phase === 'issue' && multi && (
              <div className="mt-2 space-y-2 text-sm text-slate-600">
                <p>The following printers could not be reached:</p>
                <ul className="list-disc space-y-0.5 pl-5 font-medium text-slate-800">
                  {names.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
                <p>Please check their network connections.</p>
              </div>
            )}

            {state.phase === 'checking' && (
              <p className="mt-2 text-sm text-slate-600">
                Testing {multi ? 'printer connections' : names[0] || 'printer'}…
              </p>
            )}

            {state.phase === 'restored' && (
              <p className="mt-2 text-sm text-slate-600">
                {state.detail || 'The printer is connected and ready.'}
              </p>
            )}

            {state.phase === 'failed' && (
              <div className="mt-2 flex items-start gap-2 text-sm text-slate-600">
                <XCircle className="mt-0.5 shrink-0 text-red-500" size={16} />
                <p>
                  {state.detail ||
                    'The printer is still unavailable. Please check the LAN/network connection.'}
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          {state.phase !== 'restored' && state.phase !== 'checking' && (
            <button type="button" className="ui-btn-primary" onClick={onTest}>
              {testLabel}
            </button>
          )}
          {state.phase === 'checking' ? (
            <button type="button" className="ui-btn-secondary" disabled>
              <Loader2 className="animate-spin" size={16} />
              Checking…
            </button>
          ) : (
            <button type="button" className="ui-btn-secondary" onClick={onClose}>
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
