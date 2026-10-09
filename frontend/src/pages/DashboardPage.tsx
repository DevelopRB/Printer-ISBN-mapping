import { useCallback, useEffect, useState } from 'react'
import { Download, RefreshCw } from 'lucide-react'
import { AppLayout } from '../components/AppLayout'
import { PrinterSummarySection } from '../components/PrinterSummarySection'
import { SummaryCards } from '../components/SummaryCards'
import { UploadWorkflow } from '../components/UploadWorkflow'
import { manualPrinterLabel } from '../lib/printerLabels'
import {
  checkHealth,
  createProject,
  exportUrl,
  getPrinterSummaries,
  getProject,
  getSummary,
  listProjects,
  normalizedExportUrl,
  runReconcile,
  updatePrinterNames,
  uploadListA,
  uploadPrinter,
} from '../services/api'
import type { PrinterSummary, Project, Summary } from '../types'

export function DashboardPage() {
  const [project, setProject] = useState<Project | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [printerSummaries, setPrinterSummaries] = useState<PrinterSummary[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<string>('checking…')
  const [bootstrapping, setBootstrapping] = useState(true)

  const ensurePrinterLabels = useCallback(async (p: Project) => {
    const desired = p.printers.map((pr) => ({
      slot: pr.slot,
      name: manualPrinterLabel(pr.slot),
    }))
    const needsUpdate = p.printers.some(
      (pr) => pr.name !== manualPrinterLabel(pr.slot),
    )
    if (!needsUpdate) return p
    await updatePrinterNames(p.id, desired)
    return getProject(p.id)
  }, [])

  const refreshProject = useCallback(
    async (id: number) => {
      let p = await getProject(id)
      p = await ensurePrinterLabels(p)
      setProject(p)
      return p
    },
    [ensurePrinterLabels],
  )

  const refreshDashboard = useCallback(async (id: number) => {
    const [s, ps] = await Promise.all([getSummary(id), getPrinterSummaries(id)])
    setSummary(s)
    setPrinterSummaries(ps)
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const h = await checkHealth()
        if (!cancelled) setHealth(h.status === 'ok' ? 'connected' : 'unavailable')

        const existing = await listProjects()
        let p = existing[0]
        if (!p) {
          p = await createProject()
        }
        if (cancelled) return
        p = await refreshProject(p.id)
        if (p.reconciled_at) {
          await refreshDashboard(p.id)
        }
      } catch {
        if (!cancelled) {
          setHealth('unavailable')
          setError('Cannot reach backend. Start the FastAPI server on port 8000.')
        }
      } finally {
        if (!cancelled) setBootstrapping(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshProject, refreshDashboard])

  const handleUploadListA = async (file: File) => {
    if (!project) return
    setBusy(true)
    setError(null)
    try {
      await uploadListA(project.id, file)
      await refreshProject(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  const handleUploadPrinter = async (slot: number, file: File) => {
    if (!project) return
    setBusy(true)
    setError(null)
    try {
      await updatePrinterNames(
        project.id,
        project.printers.map((pr) => ({
          slot: pr.slot,
          name: manualPrinterLabel(pr.slot),
        })),
      )
      await uploadPrinter(project.id, slot, file)
      await refreshProject(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  const handleReconcile = async () => {
    if (!project) return
    setBusy(true)
    setError(null)
    try {
      const s = await runReconcile(project.id)
      setSummary(s)
      await refreshProject(project.id)
      await refreshDashboard(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reconciliation failed.')
    } finally {
      setBusy(false)
    }
  }

  if (bootstrapping) {
    return (
      <AppLayout>
        <div className="flex min-h-[50vh] items-center justify-center text-slate-600">
          Starting Printing Reconciliation System…
        </div>
      </AppLayout>
    )
  }

  return (
    <AppLayout>
      <div>
        <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur-sm">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
            <div>
              <div className="ui-section-label mb-1">Emergency / Fallback</div>
              <h1 className="ui-page-title">Manual Reconciliation</h1>
              <p className="ui-page-subtitle">
                Upload List A and printer Excel files manually when automated download is
                unavailable. Backend {health}.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {project?.reconciled_at && (
                <>
                  <a href={exportUrl(project.id)} className="ui-btn-secondary">
                    <Download size={16} />
                    Export Detailed Report
                  </a>
                  <a href={normalizedExportUrl(project.id)} className="ui-btn-primary">
                    <Download size={16} />
                    Export Normalized Report
                  </a>
                </>
              )}
              <button
                type="button"
                className="ui-btn-secondary"
                onClick={async () => {
                  if (!project) return
                  await refreshProject(project.id)
                  if (project.reconciled_at) await refreshDashboard(project.id)
                }}
              >
                <RefreshCw size={16} />
                Refresh
              </button>
            </div>
          </div>
        </header>

        <main className="ui-page">
          {project && (
            <UploadWorkflow
              printers={project.printers}
              uploads={project.uploads}
              onUploadListA={handleUploadListA}
              onUploadPrinter={handleUploadPrinter}
              onReconcile={handleReconcile}
              busy={busy}
              error={error}
            />
          )}

          {project?.reconciled_at && (
            <>
              <section className="space-y-3">
                <h2 className="ui-section-label">Dashboard</h2>
                <SummaryCards summary={summary} />
              </section>

              <PrinterSummarySection summaries={printerSummaries} />
            </>
          )}
        </main>
      </div>
    </AppLayout>
  )
}

