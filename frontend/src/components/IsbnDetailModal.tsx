import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { getIsbnDetail } from '../services/api'
import { StatusBadge } from './StatusBadge'
import type { IsbnDetail } from '../types'

type Props = {
  projectId: number
  isbn: string
  onClose: () => void
}

export function IsbnDetailModal({ projectId, isbn, onClose }: Props) {
  const [detail, setDetail] = useState<IsbnDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getIsbnDetail(projectId, isbn)
      .then((data) => {
        if (!cancelled) setDetail(data)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load ISBN details.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, isbn])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">ISBN Detail</h2>
            <p className="font-mono text-sm text-slate-600">{isbn}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-2 text-slate-500 hover:bg-slate-100"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-6 p-5">
          {loading && <p className="text-slate-500">Loading…</p>}
          {error && <p className="text-red-700">{error}</p>}
          {detail && (
            <>
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Status
                </div>
                <StatusBadge status={detail.status} />
              </div>

              <section>
                <h3 className="mb-3 border-b border-slate-200 pb-2 text-sm font-semibold uppercase tracking-wide text-slate-700">
                  List A
                </h3>
                {detail.list_a.length === 0 ? (
                  <p className="text-sm text-slate-500">Not found in List A.</p>
                ) : (
                  <div className="space-y-4">
                    {detail.list_a.map((rec) => (
                      <dl key={rec.id} className="grid gap-2 text-sm sm:grid-cols-2">
                        <Item label="Item" value={rec.item} />
                        <Item label="Party" value={rec.party} />
                        <Item label="Voucher" value={rec.voucher_no} />
                        <Item label="Date" value={rec.date} />
                        <Item label="Pending Qty" value={rec.pending_qty} />
                        <Item label="Unit" value={rec.unit} />
                      </dl>
                    ))}
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-3 border-b border-slate-200 pb-2 text-sm font-semibold uppercase tracking-wide text-slate-700">
                  Printer Records
                </h3>
                <div className="space-y-4">
                  {detail.printer_records.map((p) => (
                    <div key={p.printer_id} className="rounded-md border border-slate-100 bg-slate-50 p-3">
                      <div className="font-medium text-slate-900">{p.printer_name}</div>
                      {!p.found ? (
                        <p className="mt-1 text-sm text-slate-500">Not found</p>
                      ) : (
                        <ul className="mt-2 space-y-2 text-sm">
                          {p.records.map((r, idx) => (
                            <li key={idx}>
                              <div className="text-slate-600">Date: {r.date || '—'}</div>
                              <div className="break-all font-mono text-xs text-slate-700">
                                {r.original_value || '—'}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function Item({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-slate-900">{value || '—'}</dd>
    </div>
  )
}
