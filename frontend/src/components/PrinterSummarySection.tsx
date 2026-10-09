import { manualPrinterLabel } from '../lib/printerLabels'
import type { PrinterSummary } from '../types'

type Props = {
  summaries: PrinterSummary[]
}

export function PrinterSummarySection({ summaries }: Props) {
  if (!summaries.length) return null

  return (
    <section className="space-y-3">
      <h2 className="ui-section-label">Printer Summary</h2>
      <div className="grid gap-3 md:grid-cols-3">
        {summaries.map((s) => (
          <div key={s.printer_id} className="ui-card-static">
            <h3 className="font-semibold text-slate-900">{manualPrinterLabel(s.slot)}</h3>
            <dl className="mt-3 space-y-1.5 text-sm">
              <Row label="Records received" value={s.records_received} />
              <Row label="Identifiers extracted" value={s.isbns_extracted} />
              <Row label="Identifier not extracted" value={s.isbns_not_extracted} />
              <Row label="Matched with List A" value={s.matched_with_list_a} />
              <Row label="Not in List A" value={s.printer_not_in_list_a ?? s.unexpected} />
            </dl>
          </div>
        ))}
      </div>
    </section>
  )
}

function Row({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium tabular-nums text-slate-900">{value.toLocaleString('en-IN')}</dd>
    </div>
  )
}
