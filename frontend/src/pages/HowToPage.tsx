import { Link } from 'react-router-dom'
import { AppLayout } from '../components/AppLayout'

export function HowToPage() {
  return (
    <AppLayout>
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6">
        <div>
          <div className="ui-section-label mb-1">Guide</div>
          <h1 className="ui-page-title">How to use</h1>
          <p className="ui-page-subtitle">
            A simple guide for Operations. When you open Printing Reconciliation, you start on{' '}
            <strong className="font-semibold text-slate-800">Automated Reconciliation</strong> — that
            is the normal daily workflow. Follow the steps below. No technical knowledge needed.
          </p>

          <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {[
              ['01', 'Upload List A'],
              ['02', 'Select Printer & Dates'],
              ['03', 'Fetch Printer Data'],
              ['04', 'Review Results'],
              ['05', 'Search ISBN'],
              ['06', 'Export Report'],
            ].map(([n, label]) => (
              <div
                key={n}
                className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-sm"
              >
                <span className="ui-step-badge text-[10px]">{n}</span>
                <span className="text-xs font-medium text-slate-800">{label}</span>
              </div>
            ))}
          </div>

          <nav className="mt-4 flex flex-wrap gap-2 text-xs">
            {[
              ['#overview', 'Overview'],
              ['#before', 'Before you start'],
              ['#list-a', 'Upload List A'],
              ['#printer-dates', 'Printer & dates'],
              ['#download', 'Download'],
              ['#printer-data', 'Printer data'],
              ['#reconcile', 'Reconciliation'],
              ['#search', 'Search ISBN'],
              ['#print-details', 'Print details'],
              ['#quantities', 'Quantities'],
              ['#export', 'Export'],
              ['#sheets', 'Excel sheets'],
              ['#statuses', 'Statuses'],
              ['#skipped', 'Skipped'],
              ['#problems', 'Problems'],
              ['#workflow', 'Quick workflow'],
            ].map(([href, label]) => (
              <a
                key={href}
                href={href}
                className="rounded-md border border-slate-200 bg-white px-2 py-1 text-slate-700 shadow-sm transition-colors duration-150 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-900"
              >
                {label}
              </a>
            ))}
          </nav>
        </div>

        {/* 1. Overview */}
        <Section id="overview" title="1. Overview">
          <p>
            Printing Reconciliation helps you compare the ISBNs sent to the printer with the books
            that were actually processed by the printer.
          </p>
          <p className="mt-2">
            The application can connect to the configured printers, retrieve printing records for a
            selected date range, identify ISBNs from printer filenames, and show whether each List A
            ISBN was found.
          </p>
          <p className="mt-2">
            You can also search for any ISBN and view its printing history, including when it was
            printed and how many copies were requested and printed.
          </p>
        </Section>

        {/* 2. Before You Start */}
        <Section id="before" title="2. Before you start">
          <p className="mb-3">Before using the application:</p>
          <ul className="list-disc space-y-2 pl-5">
            <li>Make sure your computer is connected to the office printer network.</li>
            <li>Make sure you have the correct List A Excel file.</li>
            <li>Know which printer you want to check.</li>
            <li>Know the date range you want to investigate.</li>
          </ul>
          <p className="mt-3">The application currently supports:</p>
          <ul className="mt-1 list-disc pl-5">
            <li>Printer 1</li>
            <li>Printer 2</li>
            <li>Printer 3</li>
          </ul>
          <Note>
            Optional first check: open <strong>Connect to Printer</strong> and click{' '}
            <strong>Test Connection</strong> for each printer you plan to use. If it shows{' '}
            <strong>Connected</strong>, that printer is ready. Passwords are set up by IT — they are
            never shown in the app.
          </Note>
          <div className="mt-3">
            <Link
              to="/printers"
              className="inline-flex rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
            >
              Open Connect to Printer
            </Link>
          </div>
        </Section>

        {/* 3. Upload List A */}
        <Section id="list-a" title="3. Upload List A">
          <p className="mb-3">
            List A is the list of ISBNs / books that were given to the printer for printing.
          </p>
          <ol className="list-decimal space-y-2 pl-5">
            <li>
              Open <strong>Automated Reconciliation</strong> (main page for daily use).
            </li>
            <li>
              Under <strong>Step 1 — Select List A</strong>, either choose an existing List A from
              the dropdown, or click <strong>Upload New List A</strong> and pick your Excel file.
            </li>
            <li>
              Wait for the green confirmation box showing the file name, record count, and how many
              ISBNs were detected.
            </li>
          </ol>
          <Note>
            The application keeps the original List A ISBN entries, including duplicates. You do not
            need to remove duplicate rows before uploading.
          </Note>
          <div className="mt-3">
            <Link
              to="/automated"
              className="inline-flex rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
            >
              Open Automated Reconciliation
            </Link>
          </div>
        </Section>

        {/* 4. Select Printer and Date Range */}
        <Section id="printer-dates" title="4. Select printer and date range">
          <h3 className="mb-2 text-sm font-semibold text-slate-800">Select printer</h3>
          <ol className="list-decimal space-y-2 pl-5">
            <li>
              Under <strong>Step 2 — Connect to Printer</strong>, tick the printer(s) you want.
            </li>
            <li>You can choose one printer, or more than one.</li>
            <li>
              To select everything, click <strong>Select All Printers</strong>.
            </li>
          </ol>

          <h3 className="mb-2 mt-4 text-sm font-semibold text-slate-800">Select date range</h3>
          <ol className="list-decimal space-y-2 pl-5">
            <li>
              Under <strong>Step 3 — Report Date Range</strong>, set:
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>
                  <strong>From Date</strong> — first day to include
                </li>
                <li>
                  <strong>To Date</strong> — last day to include
                </li>
              </ul>
            </li>
            <li>
              Example: From <strong>01-Aug-2026</strong> to <strong>26-Aug-2026</strong>
            </li>
          </ol>
          <p className="mt-3">
            The selected date range tells the application which period of printer activity to
            retrieve.
          </p>
          <Note>
            The selected date range is <strong>not</strong> necessarily the print date of every
            book. Each individual printer job has its own actual <strong>Print Date</strong>.
          </Note>
        </Section>

        {/* 5. Download Printer Data */}
        <Section id="download" title="5. Download printer data">
          <ol className="list-decimal space-y-2 pl-5">
            <li>
              Click <strong>Download Printer Data &amp; Reconcile</strong>.
            </li>
            <li>
              The application connects to the selected printer(s) and retrieves printing records for
              the selected date range.
            </li>
            <li>Watch the progress steps until the run finishes.</li>
          </ol>
          <p className="mt-3">After a successful download you will see details such as:</p>
          <ExampleBox>
            <div>Printer: Printer 1</div>
            <div>Report Date Range: 01-Aug-2026 → 26-Aug-2026</div>
            <div>Records Retrieved: 2,282</div>
            <div>ISBN Records: 2,254</div>
            <div>Skipped Records: 28</div>
            <div>Downloaded On: 27-Aug-2026 11:30 AM</div>
          </ExampleBox>
          <dl className="mt-4 space-y-3">
            <Term name="Report Date Range">
              The period you requested from the printer (your From / To dates).
            </Term>
            <Term name="Downloaded On">
              The date and time the application retrieved the printer information on this computer.
            </Term>
            <Term name="Print Date">
              The actual date on which an individual print job occurred (from the printer job
              record).
            </Term>
          </dl>
        </Section>

        {/* 6. Understanding Downloaded Printer Data */}
        <Section id="printer-data" title="6. Understanding downloaded printer data">
          <p className="mb-3">
            The printer provides detailed information for each printing job. The application
            extracts useful fields such as:
          </p>
          <dl className="space-y-3">
            <Term name="ISBN">The book identifier extracted from the printer&apos;s filename.</Term>
            <Term name="Print Date">The date the printer recorded for that job.</Term>
            <Term name="Job End">The time the printing job ended.</Term>
            <Term name="Print Start">The time printing started.</Term>
            <Term name="Job Accept">The time the printer accepted the job.</Term>
            <Term name="Result">The result / status reported by the printer (for example Complete).</Term>
            <Term name="Set Number">The number of sets / copies requested for the job.</Term>
            <Term name="Output Set">
              The number of sets / copies actually printed / output by the printer.
            </Term>
            <Term name="Printer">Which printer processed the job.</Term>
            <Term name="Job ID">The printer&apos;s identifier for that particular print job.</Term>
            <Term name="Source Filename">The original filename recorded by the printer.</Term>
          </dl>
        </Section>

        {/* 7. Reconciliation */}
        <Section id="reconcile" title="7. Reconciliation">
          <p>
            After printer data is downloaded, the application compares List A with the printer
            records.
          </p>
          <p className="mt-2">The reconciliation answers:</p>
          <p className="mt-1 font-medium text-slate-800">
            “Was this ISBN found in the printer records?”
          </p>
          <div className="mt-3 overflow-x-auto rounded-md border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Meaning</th>
                </tr>
              </thead>
              <tbody className="text-slate-700">
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-2 font-semibold text-green-800">PRESENT</td>
                  <td className="px-3 py-2">
                    The ISBN was found at least once in the printer records.
                  </td>
                </tr>
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-2 font-semibold text-amber-900">NOT FOUND</td>
                  <td className="px-3 py-2">
                    The ISBN was not found in the printer records retrieved for the selected date
                    range.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3">
            On the screen you will also see summary cards for Found / Not Found. In the exported
            Excel Reconciliation sheet, the Status column uses <strong>PRESENT</strong> and{' '}
            <strong>NOT FOUND</strong>.
          </p>
        </Section>

        {/* 8. Search Any ISBN */}
        <Section id="search" title="8. Search any ISBN">
          <p className="mb-3">
            Use <strong>Search an ISBN</strong> at the top of Automated Reconciliation. Enter an
            ISBN, choose a date range, and click <strong>Search</strong> — printer records are
            fetched automatically. List A is <strong>not</strong> required. You do not need to click
            Download Printer Data &amp; Reconcile first.
          </p>
          <ol className="list-decimal space-y-2 pl-5">
            <li>Select the printers to check (same checkboxes used for reconciliation).</li>
            <li>Enter the ISBN / identifier.</li>
            <li>Select From Date and To Date.</li>
            <li>
              Click <strong>Search</strong> or press Enter.
            </li>
            <li>View the result and full print history.</li>
          </ol>
          <ExampleBox>
            <div>Search: 9788182054370</div>
            <div>Range: 20-Aug-2026 → 27-Aug-2026</div>
            <div className="mt-2">ISBN: 9788182054370</div>
            <div>List A: N/A</div>
            <div>Printer: YES</div>
            <div>Status: FOUND IN PRINTER DATA</div>
            <div className="mt-2">Print History: 24-Aug-2026 · Printer 1</div>
          </ExampleBox>
          <Note>
            Search uses the date range you select each time. If an ISBN is not found, it may still
            exist outside that range — widen the dates and search again.
          </Note>
          <p className="mt-3">
            Recent searches appear under the box — click one to restore the ISBN and date range.
            Use <strong>Clear</strong> to reset the search.
          </p>
        </Section>

        {/* 9. Understanding Print Details */}
        <Section id="print-details" title="9. Understanding print details">
          <p className="mb-3">
            The application can show the complete <strong>Print History</strong> for an ISBN. If an
            ISBN was printed multiple times, each print occurrence is kept separately. The
            application does <strong>not</strong> combine or remove duplicate printer occurrences.
          </p>
          <ExampleBox>
            <div className="font-medium">ISBN: 8888001171897</div>
            <div className="mt-2 overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-500">
                    <th className="pr-3 py-1">Date</th>
                    <th className="pr-3 py-1">Printer</th>
                    <th className="pr-3 py-1">Job End</th>
                    <th className="pr-3 py-1">Print Start</th>
                    <th className="py-1">Job Accept</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="pr-3 py-1">26-Aug-2026</td>
                    <td className="pr-3 py-1">Printer 1</td>
                    <td className="pr-3 py-1">10:20:00</td>
                    <td className="pr-3 py-1">10:18:00</td>
                    <td className="py-1">10:18:00</td>
                  </tr>
                  <tr>
                    <td className="pr-3 py-1">27-Aug-2026</td>
                    <td className="pr-3 py-1">Printer 1</td>
                    <td className="pr-3 py-1">14:30:00</td>
                    <td className="pr-3 py-1">14:25:00</td>
                    <td className="py-1">14:25:00</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="mt-2 overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-500">
                    <th className="pr-3 py-1">Result</th>
                    <th className="pr-3 py-1">Set Number</th>
                    <th className="py-1">Output Set</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="pr-3 py-1">Complete</td>
                    <td className="pr-3 py-1">2</td>
                    <td className="py-1">2</td>
                  </tr>
                  <tr>
                    <td className="pr-3 py-1">Complete</td>
                    <td className="pr-3 py-1">3</td>
                    <td className="py-1">3</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </ExampleBox>
          <p className="mt-3">
            In <strong>Search ISBN</strong>, quantities may also be labelled{' '}
            <strong>Copies Requested</strong> (Set Number) and <strong>Copies Printed</strong>{' '}
            (Output Set) for easier reading.
          </p>
        </Section>

        {/* 10. Understanding Quantities */}
        <Section id="quantities" title="10. Understanding quantities">
          <div className="overflow-x-auto rounded-md border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Field</th>
                  <th className="px-3 py-2 font-medium">Meaning</th>
                </tr>
              </thead>
              <tbody className="text-slate-700">
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">Set Number</td>
                  <td className="px-3 py-2">Number of copies / sets requested</td>
                </tr>
                <tr className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">Output Set</td>
                  <td className="px-3 py-2">Number of copies / sets actually printed / output</td>
                </tr>
              </tbody>
            </table>
          </div>
          <ExampleBox>
            <div>
              <strong>Set Number: 3</strong> · <strong>Output Set: 3</strong>
            </div>
            <div className="mt-1">Means: 3 requested, 3 printed</div>
            <div className="mt-3">
              <strong>Set Number: 3</strong> · <strong>Output Set: 2</strong>
            </div>
            <div className="mt-1">Means: 3 requested, 2 printed</div>
          </ExampleBox>
          <Note>
            The application uses the values reported by the printer. It does not assume that
            requested quantity equals printed quantity.
          </Note>
        </Section>

        {/* 11. Export Normalized Report */}
        <Section id="export" title="11. Export Normalized Report">
          <ol className="list-decimal space-y-2 pl-5">
            <li>
              When processing finishes, a popup may say <strong>Ready to export your file</strong>.
            </li>
            <li>
              Click <strong>Export Normalized Report</strong> (in the popup, or on the page).
            </li>
            <li>Open the downloaded Excel file.</li>
          </ol>
          <p className="mt-3">The report helps you see:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>What was sent to the printer (List A)</li>
            <li>What the printer returned</li>
            <li>Whether each ISBN was found</li>
            <li>When it was printed and related job details</li>
            <li>Which records could not be linked to an ISBN</li>
          </ul>
          <p className="mt-3">
            You can also reopen an earlier run from <strong>Reconciliation History</strong> at the
            bottom of the page and export again without downloading from the printers.
          </p>
        </Section>

        {/* 12. Understanding the 4 Excel Sheets */}
        <Section id="sheets" title="12. Understanding the 4 Excel sheets">
          <SheetCard title="Sheet 1 — List A ISBNs">
            <p>Contains the ISBNs from the uploaded List A.</p>
            <p className="mt-2">
              <strong>Purpose:</strong> shows exactly what was provided for printing.
            </p>
            <p className="mt-2">Duplicates are preserved.</p>
          </SheetCard>

          <SheetCard title="Sheet 2 — Printer ISBNs">
            <p>
              Contains the ISBNs successfully extracted from printer records, plus printer job
              information. (If you selected more than one printer, you may see separate tabs such as{' '}
              <strong>Printer 1 ISBNs</strong>, <strong>Printer 2 ISBNs</strong>,{' '}
              <strong>Printer 3 ISBNs</strong>.)
            </p>
            <p className="mt-2 font-medium text-slate-800">Columns include:</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5">
              <li>ISBN</li>
              <li>Print Date</li>
              <li>Job End</li>
              <li>Print Start</li>
              <li>Job Accept</li>
              <li>Result</li>
              <li>Set Number (total quantity)</li>
              <li>Output Set (Printed quantity)</li>
              <li>Printer</li>
              <li>Job ID</li>
              <li>Source Filename</li>
            </ul>
            <Note>
              Duplicates are intentionally preserved. If the same ISBN was printed three times, it
              can appear three times. Rows stay in printer source order.
            </Note>
          </SheetCard>

          <SheetCard title="Sheet 3 — Reconciliation">
            <p>This is the main Operations report. It compares List A ISBNs with printer data.</p>
            <p className="mt-2 font-medium text-slate-800">It shows:</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5">
              <li>List A ISBN</li>
              <li>Printer ISBN</li>
              <li>Print Date</li>
              <li>Job End</li>
              <li>Print Start</li>
              <li>Job Accept</li>
              <li>Result</li>
              <li>Set Number (total quantity)</li>
              <li>Output Set (Printed quantity)</li>
              <li>Printer</li>
              <li>Status</li>
            </ul>
            <p className="mt-2 text-xs text-slate-500">
              Job ID and Source Filename are on the Printer ISBNs sheet(s), not on Reconciliation.
            </p>
            <p className="mt-2">
              Each List A ISBN appears once in the reconciliation view (duplicate List A rows are
              still kept as separate rows).
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>
                Found in printer data → <strong>PRESENT</strong>
              </li>
              <li>
                Not found → <strong>NOT FOUND</strong>
              </li>
            </ul>
            <p className="mt-2">
              If there were multiple print jobs for the same ISBN, the relevant print information is
              shown together on Sheet 3, while the detailed individual occurrences remain available
              on Sheet 2.
            </p>
          </SheetCard>

          <SheetCard title="Sheet 4 — Skipped ISBNs">
            <p>
              Contains printer records where the application could not extract an ISBN.
            </p>
            <p className="mt-2">Examples: CE Adjust, Details Counter, or other records without an identifiable ISBN.</p>
            <p className="mt-2">
              These records are <strong>not</strong> necessarily errors. They simply mean: the
              printer gave us a record, but there was no ISBN / identifier that the application
              could extract from it.
            </p>
            <p className="mt-2 font-medium text-slate-800">The sheet shows:</p>
            <ul className="mt-1 list-disc pl-5">
              <li>Source Row</li>
              <li>Printer Record / Filename</li>
              <li>Reason</li>
            </ul>
            <p className="mt-2">(When more than one printer was used, a Printer column may also appear.)</p>
          </SheetCard>
        </Section>

        {/* 13. Understanding Statuses */}
        <Section id="statuses" title="13. Understanding statuses">
          <div className="overflow-x-auto rounded-md border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Where you see it</th>
                  <th className="px-3 py-2 font-medium">Meaning</th>
                </tr>
              </thead>
              <tbody className="text-slate-700">
                <tr className="border-t border-slate-100 align-top">
                  <td className="px-3 py-2 font-semibold text-green-800">PRESENT</td>
                  <td className="px-3 py-2">Excel Reconciliation · Search ISBN</td>
                  <td className="px-3 py-2">
                    The ISBN is in List A and was found in the printer records.
                  </td>
                </tr>
                <tr className="border-t border-slate-100 align-top">
                  <td className="px-3 py-2 font-semibold text-amber-900">NOT FOUND</td>
                  <td className="px-3 py-2">Excel Reconciliation · Search ISBN</td>
                  <td className="px-3 py-2">
                    The ISBN was not found in the printer records for the selected date range (or was
                    not found anywhere, if you searched an unknown number).
                  </td>
                </tr>
                <tr className="border-t border-slate-100 align-top">
                  <td className="px-3 py-2 font-semibold text-sky-900">FOUND IN PRINTER DATA</td>
                  <td className="px-3 py-2">Search ISBN only</td>
                  <td className="px-3 py-2">
                    The ISBN was found in printer data but was not part of List A.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>

        {/* 14. Skipped — already covered in sheets; short dedicated note */}
        <Section id="skipped" title="14. Understanding Skipped ISBNs">
          <p>
            <strong>Skipped ISBNs</strong> are printer records without an extractable ISBN. Open
            Sheet 4 in the Excel report to see the original printer record and the reason.
          </p>
          <p className="mt-2">
            After download, the summary also shows a <strong>Skipped Records</strong> count for
            quick reference.
          </p>
        </Section>

        {/* 15. Common Problems */}
        <Section id="problems" title="15. Common problems">
          <Problem
            title="Printer not connected"
            solution='Check that your computer is connected to the office printer network and try Test Connection again. If it still fails, ask IT for help.'
          />
          <Problem
            title="No printer records found"
            solution="Check that the selected printer and date range are correct. Try a wider date range if printing may have happened on other days."
          />
          <Problem
            title="ISBN shows NOT FOUND"
            solution="Check that the selected date range includes the period when the book was printed."
          />
          <Problem
            title="ISBN appears in Skipped ISBNs"
            solution="This means the printer record did not contain an ISBN that could be extracted. Check the Skipped ISBNs sheet for the original printer record."
          />
          <Problem
            title="Search gives no result / no data available"
            solution="Select printers, enter the ISBN, choose a date range that covers when the book was printed, then click Search. Search fetches printer records automatically — List A and a prior reconciliation run are not required. If a printer shows DISCONNECTED, check Connect to Printer."
          />
          <Problem
            title="Excel report is not showing expected data"
            solution="Check that the correct List A file, printer, and date range were used."
          />
          <Problem
            title="List A will not upload"
            solution="Use a normal Excel file (.xlsx or .xls) or CSV with an ISBN column. Do not upload a Word document."
          />
        </Section>

        {/* 16. Quick Workflow */}
        <Section id="workflow" title="16. Quick workflow">
          <ol className="space-y-2 text-sm text-slate-800">
            <li className="flex items-start gap-2">
              <span className="font-semibold tabular-nums text-slate-500">1.</span>
              <span>Open Printing Reconciliation</span>
            </li>
            <li className="flex justify-center text-slate-400" aria-hidden>
              ↓
            </li>
            <li className="flex items-start gap-2">
              <span className="font-semibold tabular-nums text-slate-500">2.</span>
              <span>
                The application opens on <strong>Automated Reconciliation</strong>
              </span>
            </li>
            <li className="flex justify-center text-slate-400" aria-hidden>
              ↓
            </li>
            <li className="flex items-start gap-2">
              <span className="font-semibold tabular-nums text-slate-500">3.</span>
              <span>Upload List A</span>
            </li>
            <li className="flex justify-center text-slate-400" aria-hidden>
              ↓
            </li>
            <li className="flex items-start gap-2">
              <span className="font-semibold tabular-nums text-slate-500">4.</span>
              <span>Select Printer</span>
            </li>
            <li className="flex justify-center text-slate-400" aria-hidden>
              ↓
            </li>
            <li className="flex items-start gap-2">
              <span className="font-semibold tabular-nums text-slate-500">5.</span>
              <span>Select Date Range (From Date / To Date)</span>
            </li>
            <li className="flex justify-center text-slate-400" aria-hidden>
              ↓
            </li>
            <li className="flex items-start gap-2">
              <span className="font-semibold tabular-nums text-slate-500">6.</span>
              <span>
                Click <strong>Download Printer Data &amp; Reconcile</strong>
              </span>
            </li>
            <li className="flex justify-center text-slate-400" aria-hidden>
              ↓
            </li>
            <li className="flex items-start gap-2">
              <span className="font-semibold tabular-nums text-slate-500">7.</span>
              <span>Review processing results and reconciliation summary</span>
            </li>
            <li className="flex justify-center text-slate-400" aria-hidden>
              ↓
            </li>
            <li className="flex items-start gap-2">
              <span className="font-semibold tabular-nums text-slate-500">8.</span>
              <span>
                Use <strong>Search ISBN</strong> if you need to check one book
              </span>
            </li>
            <li className="flex justify-center text-slate-400" aria-hidden>
              ↓
            </li>
            <li className="flex items-start gap-2">
              <span className="font-semibold tabular-nums text-slate-500">9.</span>
              <span>
                Click <strong>Export Normalized Report</strong>
              </span>
            </li>
          </ol>

          <div className="mt-5 rounded-md border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600">
            <strong className="text-slate-800">Manual Reconciliation</strong> is available as an
            emergency / fallback option if automated printer retrieval cannot be used. Most days,
            stay on Automated Reconciliation.
          </div>

          <div className="mt-4">
            <Link
              to="/automated"
              className="inline-flex rounded-md bg-slate-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-700"
            >
              Start Automated Reconciliation
            </Link>
          </div>
        </Section>
      </main>
    </AppLayout>
  )
}

function Section({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: React.ReactNode
}) {
  return (
    <section id={id} className="ui-card-static scroll-mt-20">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <div className="mt-3 text-sm leading-relaxed text-slate-600">{children}</div>
    </section>
  )
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="ui-alert-warn mt-3">
      <strong>Important:</strong> {children}
    </div>
  )
}

function ExampleBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 font-mono text-xs leading-relaxed text-slate-800">
      {children}
    </div>
  )
}

function Term({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="font-medium text-slate-800">{name}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  )
}

function SheetCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-3 rounded-lg border border-blue-100 bg-blue-50/40 px-3 py-3">
      <div className="font-medium text-slate-800">{title}</div>
      <div className="mt-2 text-sm leading-relaxed text-slate-600">{children}</div>
    </div>
  )
}

function Problem({ title, solution }: { title: string; solution: string }) {
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <div className="font-medium text-slate-800">Problem: {title}</div>
      <div className="mt-1 text-sm text-slate-600">
        <strong>Solution:</strong> {solution}
      </div>
    </div>
  )
}
