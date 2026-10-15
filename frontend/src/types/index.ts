export type Printer = {

  id: number

  slot: number

  name: string

}



export type Upload = {

  id: number

  upload_type: string

  printer_id: number | null

  filename: string

  record_count: number

  isbn_detected_count: number

  isbn_column?: string | null

  source_column?: string | null

  uploaded_at: string

}



export type Project = {

  id: number

  name: string

  created_at: string

  reconciled_at: string | null

  printers: Printer[]

  uploads: Upload[]

}



export type Summary = {

  list_a_records: number

  unique_isbns: number

  found: number

  not_found: number

  duplicates: number

  needs_review: number

  printer_records: number

  printer_isbns: number

  printer_not_in_list_a: number

  printer_without_isbn: number

  total_results: number

  // aliases

  matched?: number

  not_reported?: number

  unexpected?: number

  invalid?: number

  multiple_occurrences?: number

  isbn_not_found?: number

}



export type PrinterSummary = {

  printer_id: number

  printer_name: string

  slot: number

  records_received: number

  isbns_extracted: number

  isbns_not_extracted: number

  matched_with_list_a: number

  unexpected: number

  printer_not_in_list_a?: number

}



export type ReconciliationRow = {

  id: number

  isbn: string | null

  status: string

  item: string | null

  party: string | null

  voucher_no: string | null

  list_a_date: string | null

  pending_qty: string | null

  printer_names: string[]

  printer_dates: string[]

  original_printer_values: string[]

  source: string | null

  list_a_record_ids: number[]

  printer_record_ids: number[]

  printer_occurrences?: number

}



export type PaginatedResults = {

  total: number

  page: number

  page_size: number

  items: ReconciliationRow[]

}



export type IsbnDetail = {

  isbn: string

  status: string

  list_a: Array<{

    id: number

    item: string | null

    party: string | null

    voucher_no: string | null

    date: string | null

    pending_qty: string | null

    unit: string | null

    isbn_original: string | null

  }>

  printer_records: Array<{

    printer_id: number

    printer_name: string

    found: boolean

    records: Array<{

      date: string | null

      original_value: string | null

      source_row_number: number

    }>

  }>

}



export type ResultFilters = {

  status?: string

  printer?: string

  party?: string

  isbn?: string

  item?: string

  voucher_no?: string

  date?: string

  page?: number

  page_size?: number

}



export type NetworkPrinterConfig = {

  id: number

  slot: number

  name: string

  protocol: string

  host: string

  port: number

  joblog_path: string

  base_url: string

  joblog_url: string

  display_endpoint: string

  username_env: string

  password_env: string

  username_configured: boolean

  password_configured: boolean

  is_enabled: boolean

  last_connection_ok: boolean | null

  last_connection_category: string | null

  last_connection_message: string | null

  last_connection_http_status: number | null

  last_connection_latency_ms: number | null

  last_checked_at: string | null

  verify_ssl: boolean

  endpoint_options?: { protocol: string; port: number; display_endpoint: string }[]

}



export type ConnectionTestResult = {

  slot: number

  name: string

  display_endpoint: string

  ok: boolean

  category: string

  message: string

  http_status: number | null

  latency_ms: number | null

  checked_at: string

  password_configured: boolean

}



export type ListAUploadInfo = {

  id: number

  filename: string

  record_count: number

  isbn_detected_count: number

  isbn_column?: string | null

  uploaded_at: string

  project_id: number

}



export type RunStep = {

  key: string

  label: string

  status: string

  detail?: string | null

  printer_slot?: number

}



export type PrinterDownloadInfo = {

  id: number

  printer_slot: number

  printer_name: string

  start_date: string

  end_date: string

  filename: string | null

  retrieved_at: string | null

  record_count: number

  file_size: number

  status: string

  error_message: string | null

}



export type AutomatedRunSummary = {

  list_a_records: number

  unique_isbns: number

  found: number

  not_found: number

  duplicates: number

  needs_review: number

  printer_records: number

  printer_isbns: number

  valid_isbns: number

  printer_not_in_list_a: number

  printer_without_isbn: number

  printers_ok?: number

  printers_failed?: number

  printer_slots?: number[]

  matched?: number

  not_reported?: number

  unexpected?: number

  multiple_occurrences?: number

}



export type AutomatedRun = {

  id: number

  list_a_upload_id: number | null

  list_a_filename: string | null

  list_a_record_count: number

  list_a_isbn_count: number

  printer_slots: number[]

  start_date: string

  end_date: string

  status: string

  steps: RunStep[]

  summary: AutomatedRunSummary | null

  error_message: string | null

  started_at: string

  completed_at: string | null

  downloads: PrinterDownloadInfo[]

}



export type AutomatedResultRow = {

  id: number

  isbn: string | null

  status: string

  item: string | null

  party: string | null

  voucher_no: string | null

  list_a_date: string | null

  pending_qty: string | null

  printer_names: string[]

  printer_dates: string[]

  original_printer_values: string[]

  source: string | null

  printer_occurrences?: number

}



export type PaginatedAutomatedResults = {

  total: number

  page: number

  page_size: number

  items: AutomatedResultRow[]

}



export type PrinterSearchOccurrence = {

  isbn: string

  print_date: string | null

  printer_name: string

  printer_slot: number

  source_filename: string | null

  source_row: number | null

  job_id?: string | null

  job_end?: string | null

  print_start?: string | null

  job_accept?: string | null

  result?: string | null

  set_number?: string | null

  output_set?: string | null

}



export type RunSearchData = {

  run_id: number

  start_date?: string | null

  end_date?: string | null

  list_a_isbns: string[]

  printer_occurrences: PrinterSearchOccurrence[]

}



export type IsbnSearchStatus =
  | 'PRESENT'
  | 'NOT FOUND'
  | 'FOUND IN PRINTER DATA'



export type IsbnSearchResult = {

  query: string

  normalizedIsbn: string

  /** null = no List A loaded for this search */
  listA: boolean | null

  printer: boolean

  status: IsbnSearchStatus

  occurrences: PrinterSearchOccurrence[]

  startDate?: string | null

  endDate?: string | null

  printersSearched?: { slot: number; name: string; ok: boolean; error?: string | null }[]

}



export type DirectIsbnSearchResponse = {

  query: string

  normalized_isbn: string

  start_date: string

  end_date: string

  list_a: boolean | null

  printer: boolean

  status: string

  occurrences: PrinterSearchOccurrence[]

  printers: {

    slot: number

    name: string

    ok: boolean

    record_count: number

    match_count: number

    error: string | null

  }[]

  steps: { label?: string; status?: string; detail?: string; printer_slot?: number }[]

}


export type DirectBatchItemResponse = {
  query: string
  normalized_isbn: string
  list_a: boolean | null
  printer: boolean
  status: string
  occurrences: PrinterSearchOccurrence[]
}

export type DirectMultiIsbnSearchResponse = {
  start_date: string
  end_date: string
  entered_count: number
  unique_count: number
  found_count: number
  not_found_count: number
  connection_issue_count: number
  results: DirectBatchItemResponse[]
  printers: {
    slot: number
    name: string
    ok: boolean
    record_count: number
    match_count: number
    error: string | null
  }[]
  steps: { label?: string; status?: string; detail?: string; printer_slot?: number }[]
}
