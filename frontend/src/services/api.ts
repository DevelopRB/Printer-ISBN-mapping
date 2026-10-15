import axios from 'axios'
import type {
  AutomatedRun,
  ConnectionTestResult,
  DirectIsbnSearchResponse,
  DirectMultiIsbnSearchResponse,
  IsbnDetail,
  ListAUploadInfo,
  NetworkPrinterConfig,
  PaginatedAutomatedResults,
  PaginatedResults,
  Printer,
  PrinterSummary,
  Project,
  ResultFilters,
  RunSearchData,
  Summary,
  Upload,
} from '../types'

const apiBase = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') || '/api'

const api = axios.create({
  baseURL: apiBase,
  timeout: 120000,
})

/** Absolute or root-relative API path for window.open / download links. */
export function apiPath(path: string): string {
  const clean = path.startsWith('/') ? path : `/${path}`
  if (apiBase.startsWith('http')) {
    return `${apiBase}${clean}`
  }
  return `${apiBase}${clean}`
}

function errorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
    }
  }
  return fallback
}

export async function checkHealth(): Promise<{ status: string; service: string }> {
  const { data } = await api.get('/health')
  return data
}

export async function createProject(name = 'Printing Reconciliation'): Promise<Project> {
  const { data } = await api.post('/projects', {
    name,
    printers: [
      { slot: 1, name: 'Printer 1 (192.168.2.7)' },
      { slot: 2, name: 'Printer 2 (192.168.2.218)' },
      { slot: 3, name: 'Printer 3 (192.168.2.176)' },
    ],
  })
  return data
}

export async function getProject(id: number): Promise<Project> {
  const { data } = await api.get(`/projects/${id}`)
  return data
}

export async function listProjects(): Promise<Project[]> {
  const { data } = await api.get('/projects')
  return data
}

export async function updatePrinterNames(
  projectId: number,
  printers: { slot: number; name: string }[],
): Promise<Printer[]> {
  const { data } = await api.patch(`/projects/${projectId}/printers`, printers)
  return data
}

export async function uploadListA(projectId: number, file: File): Promise<Upload> {
  const form = new FormData()
  form.append('file', file)
  try {
    const { data } = await api.post(`/projects/${projectId}/upload/list-a`, form)
    return data
  } catch (err) {
    throw new Error(errorMessage(err, 'Failed to upload List A.'))
  }
}

export async function uploadPrinter(
  projectId: number,
  printerSlot: number,
  file: File,
): Promise<Upload> {
  const form = new FormData()
  form.append('file', file)
  form.append('printer_slot', String(printerSlot))
  try {
    const { data } = await api.post(`/projects/${projectId}/upload/printer`, form)
    return data
  } catch (err) {
    throw new Error(errorMessage(err, 'Failed to upload printer file.'))
  }
}

export async function runReconcile(projectId: number): Promise<Summary> {
  try {
    const { data } = await api.post(`/projects/${projectId}/reconcile`)
    return data
  } catch (err) {
    throw new Error(errorMessage(err, 'Reconciliation failed.'))
  }
}

export async function getSummary(projectId: number): Promise<Summary> {
  const { data } = await api.get(`/projects/${projectId}/summary`)
  return data
}

export async function getPrinterSummaries(projectId: number): Promise<PrinterSummary[]> {
  const { data } = await api.get(`/projects/${projectId}/printer-summaries`)
  return data
}

export async function getResults(
  projectId: number,
  filters: ResultFilters = {},
): Promise<PaginatedResults> {
  const { data } = await api.get(`/projects/${projectId}/results`, { params: filters })
  return data
}

export async function getIsbnDetail(projectId: number, isbn: string): Promise<IsbnDetail> {
  const { data } = await api.get(`/projects/${projectId}/isbn/${isbn}`)
  return data
}

export function exportUrl(projectId: number): string {
  return apiPath(`/projects/${projectId}/export`)
}

export function normalizedExportUrl(projectId: number): string {
  return apiPath(`/projects/${projectId}/export/normalized`)
}

export async function listNetworkPrinters(): Promise<NetworkPrinterConfig[]> {
  const { data } = await api.get('/network-printers')
  return data
}

export async function updateNetworkPrinter(
  slot: number,
  payload: Partial<{
    name: string
    protocol: string
    host: string
    port: number
    joblog_path: string
    is_enabled: boolean
  }>,
): Promise<NetworkPrinterConfig> {
  const { data } = await api.patch(`/network-printers/${slot}`, payload)
  return data
}

/** Saves the printer login on this computer. A blank password keeps the saved one. */
export async function savePrinterCredentials(
  slot: number,
  payload: { username: string; password?: string },
): Promise<NetworkPrinterConfig> {
  try {
    const { data } = await api.put(`/network-printers/${slot}/credentials`, payload)
    return data
  } catch (err) {
    throw new Error(errorMessage(err, 'Could not save the printer login.'))
  }
}

export async function testNetworkPrinterConnection(
  slot: number,
): Promise<ConnectionTestResult> {
  try {
    // Backend TCP/HTTP timeout is ~8s; keep client ceiling slightly above that.
    const { data } = await api.post(`/network-printers/${slot}/test-connection`, null, {
      timeout: 20000,
    })
    return data
  } catch (err) {
    throw new Error(errorMessage(err, 'Connection test failed.'))
  }
}

export async function listListAUploads(): Promise<ListAUploadInfo[]> {
  const { data } = await api.get('/reconciliation/list-a')
  return data
}

export async function uploadListAForAutomation(file: File): Promise<ListAUploadInfo> {
  const form = new FormData()
  form.append('file', file)
  try {
    const { data } = await api.post('/reconciliation/list-a/upload', form)
    return data
  } catch (err) {
    throw new Error(errorMessage(err, 'Failed to upload List A.'))
  }
}

export async function startAutomatedRun(payload: {
  list_a_id?: number | null
  printer_ids: number[]
  start_date: string
  end_date: string
}): Promise<AutomatedRun> {
  try {
    const { data } = await api.post('/reconciliation/run', {
      list_a_id: payload.list_a_id ?? null,
      printer_ids: payload.printer_ids,
      start_date: payload.start_date,
      end_date: payload.end_date,
    })
    return data
  } catch (err) {
    throw new Error(errorMessage(err, 'Failed to start reconciliation.'))
  }
}

export async function getAutomatedRun(runId: number): Promise<AutomatedRun> {
  const { data } = await api.get(`/reconciliation/run/${runId}`)
  return data
}

export async function listAutomatedRuns(): Promise<AutomatedRun[]> {
  const { data } = await api.get('/reconciliation/runs')
  return data
}

export async function getAutomatedResults(
  runId: number,
  params: { page?: number; page_size?: number; status?: string; isbn?: string; printer?: string } = {},
): Promise<PaginatedAutomatedResults> {
  const { data } = await api.get(`/reconciliation/run/${runId}/results`, { params })
  return data
}

export async function getAutomatedPrinterRecords(
  runId: number,
  params: { page?: number; page_size?: number } = {},
): Promise<PaginatedAutomatedResults> {
  const { data } = await api.get(`/reconciliation/run/${runId}/printer-records`, { params })
  return data
}

export async function getAutomatedSearchData(runId: number): Promise<RunSearchData> {
  try {
    const { data } = await api.get(`/reconciliation/run/${runId}/search-data`)
    return data
  } catch (err) {
    throw new Error(errorMessage(err, 'Failed to load ISBN search data.'))
  }
}

export async function directIsbnSearch(payload: {
  isbn: string
  printer_ids: number[]
  start_date: string
  end_date: string
  list_a_id?: number | null
}): Promise<DirectIsbnSearchResponse> {
  try {
    const { data } = await api.post(
      '/reconciliation/search-isbn',
      {
        isbn: payload.isbn,
        printer_ids: payload.printer_ids,
        start_date: payload.start_date,
        end_date: payload.end_date,
        list_a_id: payload.list_a_id ?? null,
      },
      { timeout: 300000 },
    )
    return data
  } catch (err) {
    throw new Error(
      errorMessage(err, 'Could not retrieve printer records. Please check printer connectivity and try again.'),
    )
  }
}

export async function directMultiIsbnSearch(payload: {
  isbns: string[]
  printer_ids: number[]
  start_date: string
  end_date: string
  list_a_id?: number | null
  entered_count?: number
}): Promise<DirectMultiIsbnSearchResponse> {
  try {
    const { data } = await api.post(
      '/reconciliation/search-isbns',
      {
        isbns: payload.isbns,
        printer_ids: payload.printer_ids,
        start_date: payload.start_date,
        end_date: payload.end_date,
        list_a_id: payload.list_a_id ?? null,
        entered_count: payload.entered_count ?? payload.isbns.length,
      },
      { timeout: 300000 },
    )
    return data
  } catch (err) {
    throw new Error(
      errorMessage(err, 'Could not retrieve printer records. Please check printer connectivity and try again.'),
    )
  }
}

export type SearchResultExportRow = {
  isbn: string
  list_a: string
  printer: string
  /** Same printer print_date shown in Search Results UI (ISO or display form). */
  print_date: string
  job_end: string
  print_start: string
  job_accept: string
  result: string
  set_number: string
  output_set: string
  source_filename: string
  status: string
}

/** Download Excel for already-displayed Search Results (no printer refetch). */
export async function exportSearchResults(rows: SearchResultExportRow[]): Promise<void> {
  try {
    const { data } = await api.post(
      '/reconciliation/search-results/export',
      { rows },
      { responseType: 'blob', timeout: 120000 },
    )
    const blob = data instanceof Blob ? data : new Blob([data])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'ISBN_Search_Results.xlsx'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (err) {
    throw new Error(errorMessage(err, 'Failed to export search results.'))
  }
}

export async function retryFailedPrinters(runId: number): Promise<AutomatedRun> {
  const { data } = await api.post(`/reconciliation/run/${runId}/retry-failed`)
  return data
}

export function automatedExportUrl(runId: number): string {
  return apiPath(`/reconciliation/run/${runId}/export`)
}

export function automatedNormalizedExportUrl(runId: number): string {
  return apiPath(`/reconciliation/run/${runId}/export/normalized`)
}

export { errorMessage }
