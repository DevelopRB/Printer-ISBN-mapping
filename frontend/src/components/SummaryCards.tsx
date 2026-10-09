import type { Summary } from '../types'

type CardDef = {
  key: keyof Summary
  label: string
  filterStatus?: string
  accent?: string
}

const LIST_A_CARDS: CardDef[] = [
  { key: 'unique_isbns', label: 'List A ISBNs', accent: 'border-l-slate-600' },
  { key: 'found', label: 'Found', filterStatus: 'FOUND', accent: 'border-l-green-600' },
  { key: 'not_found', label: 'Not Found', filterStatus: 'NOT_FOUND', accent: 'border-l-amber-500' },
  {
    key: 'duplicates',
    label: 'Duplicate List A',
    filterStatus: 'DUPLICATE_IN_LIST_A',
    accent: 'border-l-violet-500',
  },
  {
    key: 'needs_review',
    label: 'Needs Review',
    filterStatus: 'NEEDS_REVIEW',
    accent: 'border-l-orange-500',
  },
]

const AUDIT_CARDS: CardDef[] = [
  { key: 'printer_isbns', label: 'Printer Identifiers', accent: 'border-l-slate-500' },
  {
    key: 'printer_not_in_list_a',
    label: 'Not in List A',
    filterStatus: 'PRINTER_RECORDS_NOT_IN_LIST_A',
    accent: 'border-l-sky-600',
  },
  {
    key: 'printer_without_isbn',
    label: 'Identifier Not Extracted',
    filterStatus: 'ISBN_NOT_FOUND',
    accent: 'border-l-slate-400',
  },
]

function formatNumber(n: number) {
  return n.toLocaleString('en-IN')
}

type Props = {
  summary: Summary | null
  activeFilter?: string
  onFilter?: (status?: string) => void
}

function CardGrid({
  cards,
  summary,
  activeFilter,
  onFilter,
}: {
  cards: CardDef[]
  summary: Summary | null
  activeFilter?: string
  onFilter?: (status?: string) => void
}) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      {cards.map((card) => {
        const value = summary?.[card.key] ?? 0
        const clickable = Boolean(card.filterStatus && onFilter)
        const active = activeFilter === card.filterStatus
        return (
          <button
            key={card.key}
            type="button"
            disabled={!clickable}
            onClick={() => {
              if (!card.filterStatus || !onFilter) return
              onFilter(active ? undefined : card.filterStatus)
            }}
            className={`rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm transition duration-150 border-l-4 ${card.accent} ${
              clickable ? 'hover:border-slate-300 hover:shadow-md cursor-pointer' : 'cursor-default'
            } ${active ? 'ring-2 ring-blue-500/40' : ''}`}
          >
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {card.label}
            </div>
            <div className="mt-2 text-2xl font-semibold text-slate-900 tabular-nums">
              {formatNumber(typeof value === 'number' ? value : 0)}
            </div>
          </button>
        )
      })}
    </div>
  )
}

export function SummaryCards({ summary, activeFilter, onFilter }: Props) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">
          List A Reconciliation
        </h2>
        <CardGrid
          cards={LIST_A_CARDS}
          summary={summary}
          activeFilter={activeFilter}
          onFilter={onFilter}
        />
      </div>
      <div>
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-600">
          Printer Audit
        </h2>
        <p className="mb-3 text-xs text-slate-500">
          Separate from List A — printer identifiers that were not on the selected List A, or could
          not be extracted.
        </p>
        <CardGrid
          cards={AUDIT_CARDS}
          summary={summary}
          activeFilter={activeFilter}
          onFilter={onFilter}
        />
      </div>
    </div>
  )
}
