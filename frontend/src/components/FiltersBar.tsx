import type { ResultFilters } from '../types'

type Props = {
  filters: ResultFilters
  onChange: (next: ResultFilters) => void
  printers: string[]
}

const STATUSES = [
  '',
  'FOUND',
  'NOT_FOUND',
  'DUPLICATE_IN_LIST_A',
  'NEEDS_REVIEW',
  'PRINTER_RECORDS_NOT_IN_LIST_A',
  'ISBN_NOT_FOUND',
]

export function FiltersBar({ filters, onChange, printers }: Props) {
  const set = (key: keyof ResultFilters, value: string) => {
    onChange({ ...filters, [key]: value || undefined, page: 1 })
  }

  return (
    <div className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-3 xl:grid-cols-4">
      <Field label="Status">
        <select
          className="input"
          value={filters.status || ''}
          onChange={(e) => set('status', e.target.value)}
        >
          <option value="">All statuses</option>
          {STATUSES.filter(Boolean).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Printer">
        <select
          className="input"
          value={filters.printer || ''}
          onChange={(e) => set('printer', e.target.value)}
        >
          <option value="">All printers</option>
          {printers.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </Field>
      <Field label="ISBN (partial OK)">
        <input
          className="input"
          placeholder="e.g. 937225"
          value={filters.isbn || ''}
          onChange={(e) => set('isbn', e.target.value)}
        />
      </Field>
      <Field label="Party">
        <input
          className="input"
          value={filters.party || ''}
          onChange={(e) => set('party', e.target.value)}
        />
      </Field>
      <Field label="Book / Item">
        <input
          className="input"
          value={filters.item || ''}
          onChange={(e) => set('item', e.target.value)}
        />
      </Field>
      <Field label="Voucher No.">
        <input
          className="input"
          value={filters.voucher_no || ''}
          onChange={(e) => set('voucher_no', e.target.value)}
        />
      </Field>
      <Field label="Date">
        <input
          className="input"
          value={filters.date || ''}
          onChange={(e) => set('date', e.target.value)}
        />
      </Field>
      <div className="flex items-end">
        <button
          type="button"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
          onClick={() => onChange({ page: 1, page_size: filters.page_size || 50 })}
        >
          Clear filters
        </button>
      </div>
      <style>{`
        .input {
          width: 100%;
          border: 1px solid #e2e8f0;
          border-radius: 0.375rem;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          background: white;
        }
        .input:focus {
          outline: 2px solid #94a3b8;
          outline-offset: 1px;
        }
      `}</style>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs font-medium text-slate-600">
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  )
}
