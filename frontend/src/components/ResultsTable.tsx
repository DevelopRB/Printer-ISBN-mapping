import { StatusBadge } from './StatusBadge'

import type { ReconciliationRow } from '../types'



type Props = {

  rows: ReconciliationRow[]

  loading?: boolean

  onIsbnClick: (isbn: string) => void

}



function display(value: string | null | undefined) {

  return value && value.trim() ? value : '—'

}



export function ResultsTable({ rows, loading, onIsbnClick }: Props) {

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

            {loading && (

              <tr>

                <td colSpan={10} className="px-3 py-8 text-center text-slate-500">

                  Loading results…

                </td>

              </tr>

            )}

            {!loading && rows.length === 0 && (

              <tr>

                <td colSpan={10} className="px-3 py-8 text-center text-slate-500">

                  No results. Upload files and run reconciliation.

                </td>

              </tr>

            )}

            {!loading &&

              rows.map((row) => (

                <tr key={row.id} className="hover:bg-slate-50/80">

                  <td className="px-3 py-2 align-top">

                    <StatusBadge status={row.status} />

                  </td>

                  <td className="px-3 py-2 align-top font-mono text-xs">

                    {row.isbn ? (

                      <button

                        type="button"

                        className="text-sky-800 underline-offset-2 hover:underline"

                        onClick={() => onIsbnClick(row.isbn!)}

                      >

                        {row.isbn}

                      </button>

                    ) : (

                      '—'

                    )}

                  </td>

                  <td className="px-3 py-2 align-top max-w-[220px] truncate" title={row.item || ''}>

                    {display(row.item)}

                  </td>

                  <td className="px-3 py-2 align-top max-w-[180px] truncate" title={row.party || ''}>

                    {display(row.party)}

                  </td>

                  <td className="px-3 py-2 align-top">{display(row.voucher_no)}</td>

                  <td className="px-3 py-2 align-top whitespace-nowrap">{display(row.list_a_date)}</td>

                  <td className="px-3 py-2 align-top tabular-nums">{display(row.pending_qty)}</td>

                  <td className="px-3 py-2 align-top">

                    {row.printer_names.length ? row.printer_names.join(', ') : '—'}

                  </td>

                  <td className="px-3 py-2 align-top">

                    {row.printer_dates.filter(Boolean).join(', ') || '—'}

                  </td>

                  <td className="px-3 py-2 align-top tabular-nums">

                    {row.printer_occurrences ?? row.printer_record_ids?.length ?? 0}

                  </td>

                </tr>

              ))}

          </tbody>

        </table>

      </div>

    </div>

  )

}


