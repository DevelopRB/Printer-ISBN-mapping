import { useRef, useState } from 'react'
import { CheckCircle2, FileSpreadsheet, Loader2, Upload } from 'lucide-react'
import { manualPrinterLabel } from '../lib/printerLabels'
import type { Printer, Upload as UploadType } from '../types'

type Props = {
  printers: Printer[]
  uploads: UploadType[]
  onUploadListA: (file: File) => Promise<void>
  onUploadPrinter: (slot: number, file: File) => Promise<void>
  onReconcile: () => Promise<void>
  busy: boolean
  error: string | null
}

export function UploadWorkflow({
  printers,
  uploads,
  onUploadListA,
  onUploadPrinter,
  onReconcile,
  busy,
  error,
}: Props) {
  const listA = uploads.find((u) => u.upload_type === 'list_a')
  const printerUploadById = new Map(
    uploads.filter((u) => u.upload_type === 'printer' && u.printer_id != null).map((u) => [u.printer_id!, u]),
  )

  const canReconcile = Boolean(listA) && printers.some((p) => printerUploadById.has(p.id))

  return (
    <div className="ui-card-static space-y-6">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Upload Workflow</h2>
        <p className="mt-1 text-sm text-slate-500">
          List A (books that were given to the printer for printing) is the source of truth.
          Printer files are production records — only ISBNs are extracted for matching.
        </p>
      </div>

      <Step title="Step 1 — Upload List A (books that were given to the printer for printing)">
        <FilePicker
          label="Choose Excel / CSV"
          accept=".xlsx,.xls,.csv"
          disabled={busy}
          onFile={onUploadListA}
        />
        {listA && (
          <SuccessNote
            title="List A loaded"
            lines={[
              `File: ${listA.filename}`,
              `Records: ${listA.record_count.toLocaleString('en-IN')}`,
              `ISBNs detected: ${listA.isbn_detected_count.toLocaleString('en-IN')}`,
              listA.isbn_column ? `ISBN column: ${listA.isbn_column}` : '',
            ]}
          />
        )}
      </Step>

      <Step title="Step 2 — Printer files">
        <div className="grid gap-4 md:grid-cols-3">
          {printers.map((p) => {
            const up = printerUploadById.get(p.id)
            const label = manualPrinterLabel(p.slot)
            return (
              <div key={p.id} className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
                <div className="mb-2 text-sm font-medium text-slate-800">{label}</div>
                <FilePicker
                  label="Choose Excel File"
                  accept=".xlsx,.xls,.csv"
                  disabled={busy}
                  onFile={(f) => onUploadPrinter(p.slot, f)}
                />
                {up && (
                  <SuccessNote
                    title="Loaded"
                    lines={[
                      up.filename,
                      `Records: ${up.record_count.toLocaleString('en-IN')}`,
                      `ISBNs: ${up.isbn_detected_count.toLocaleString('en-IN')}`,
                      up.source_column ? `Field: ${up.source_column}` : '',
                    ]}
                  />
                )}
              </div>
            )
          })}
        </div>
      </Step>

      <Step title="Step 3 — Run reconciliation">
        <button
          type="button"
          disabled={!canReconcile || busy}
          onClick={() => void onReconcile()}
          className="ui-btn-primary"
        >
          {busy ? <Loader2 className="animate-spin" size={16} /> : <FileSpreadsheet size={16} />}
          Run Reconciliation
        </button>
        {!canReconcile && (
          <p className="mt-2 text-sm text-slate-500">
            Upload List A and at least one printer file to continue.
          </p>
        )}
      </Step>

      {error && <div className="ui-alert-error">{error}</div>}
    </div>
  )
}

function Step({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>
      {children}
    </section>
  )
}

function FilePicker({
  label,
  accept,
  disabled,
  onFile,
}: {
  label: string
  accept: string
  disabled?: boolean
  onFile: (file: File) => Promise<void> | void
}) {
  const ref = useRef<HTMLInputElement>(null)
  const [localBusy, setLocalBusy] = useState(false)

  return (
    <div>
      <input
        ref={ref}
        type="file"
        accept={accept}
        className="hidden"
        disabled={disabled || localBusy}
        onChange={async (e) => {
          const file = e.target.files?.[0]
          e.target.value = ''
          if (!file) return
          setLocalBusy(true)
          try {
            await onFile(file)
          } finally {
            setLocalBusy(false)
          }
        }}
      />
      <button
        type="button"
        disabled={disabled || localBusy}
        onClick={() => ref.current?.click()}
        className="ui-btn-secondary"
      >
        {localBusy ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}
        {localBusy ? 'Uploading…' : label}
      </button>
    </div>
  )
}

function SuccessNote({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="mt-3 flex gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900">
      <CheckCircle2 className="mt-0.5 shrink-0" size={16} />
      <div>
        <div className="font-medium">{title}</div>
        {lines.filter(Boolean).map((line) => (
          <div key={line} className="text-green-800/90">
            {line}
          </div>
        ))}
      </div>
    </div>
  )
}

