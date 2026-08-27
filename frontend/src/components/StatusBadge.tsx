const STATUS_STYLES: Record<string, string> = {

  FOUND: 'bg-green-100 text-green-800 border-green-200',

  NOT_FOUND: 'bg-amber-100 text-amber-900 border-amber-200',

  DUPLICATE_IN_LIST_A: 'bg-violet-100 text-violet-800 border-violet-200',

  NEEDS_REVIEW: 'bg-orange-100 text-orange-800 border-orange-200',

  PRINTER_RECORDS_NOT_IN_LIST_A: 'bg-sky-100 text-sky-800 border-sky-200',

  ISBN_NOT_FOUND: 'bg-slate-100 text-slate-700 border-slate-200',

  MATCHED: 'bg-green-100 text-green-800 border-green-200',

  NOT_REPORTED: 'bg-amber-100 text-amber-900 border-amber-200',

  UNEXPECTED_PRINTER_ISBN: 'bg-sky-100 text-sky-800 border-sky-200',

  INVALID_ISBN: 'bg-orange-100 text-orange-800 border-orange-200',

  MULTIPLE_PRINTER_OCCURRENCES: 'bg-green-100 text-green-800 border-green-200',

}



const STATUS_LABELS: Record<string, string> = {

  FOUND: 'FOUND',

  NOT_FOUND: 'NOT FOUND',

  DUPLICATE_IN_LIST_A: 'DUPLICATE IN LIST A',

  NEEDS_REVIEW: 'NEEDS REVIEW',

  PRINTER_RECORDS_NOT_IN_LIST_A: 'NOT IN LIST A',

  ISBN_NOT_FOUND: 'IDENTIFIER NOT EXTRACTED',

  MATCHED: 'FOUND',

  NOT_REPORTED: 'NOT FOUND',

  UNEXPECTED_PRINTER_ISBN: 'NOT IN LIST A',

  INVALID_ISBN: 'NEEDS REVIEW',

  MULTIPLE_PRINTER_OCCURRENCES: 'FOUND',

}



export function StatusBadge({ status }: { status: string }) {

  const cls = STATUS_STYLES[status] || 'bg-slate-100 text-slate-700 border-slate-200'

  const label = STATUS_LABELS[status] || status

  return (

    <span

      className={`inline-flex whitespace-nowrap rounded border px-2 py-0.5 text-xs font-semibold tracking-wide ${cls}`}

    >

      {label}

    </span>

  )

}


