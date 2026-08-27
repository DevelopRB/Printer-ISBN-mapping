import { Link } from 'react-router-dom'
import { AppLayout } from '../components/AppLayout'

export function HowToPage() {
  return (
    <AppLayout>
      <main className="mx-auto max-w-3xl space-y-8 px-4 py-6 sm:px-6">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">How to use this app</h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            This guide explains, in simple steps, how to check whether books from your List A were
            printed on Printer 1, Printer 2, or Printer 3. You do not need any technical knowledge.
          </p>
        </div>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">What this app does</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            You have a list of book numbers (ISBNs) in an Excel file called List A. The printers also
            keep a record of what they printed. This app downloads those printer records for the
            dates you choose, finds the book numbers in the printer filenames, and tells you which
            List A books were printed and which were not. At the end you download one Excel report.
          </p>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">Before you start</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-slate-600">
            <li>Sit at a computer that is connected to the office printer network.</li>
            <li>
              Keep your List A Excel file ready — usually a file with the list of ISBNs that you give to the printer, or that you keep with yourself.
            </li>
            <li>Know which dates you want to check (for example: 1 August to 26 August).</li>
            <li>
              If a printer password was never set up on this computer, ask IT for help first. You
              will not type passwords inside this app.
            </li>
          </ol>
        </section>

        <Step
          number={1}
          title="Connect to the printers"
          linkTo="/printers"
          linkLabel="Open Connect to Printer"
        >
          <p>This step only checks that each printer is reachable. It does not download book data yet.</p>
          <ol className="mt-3 list-decimal space-y-2 pl-5">
            <li>
              Click <strong>Connect to Printer</strong> at the top of the screen.
            </li>
            <li>
              You will see Printer 1, Printer 2, and Printer 3.
            </li>
            <li>
              For each printer you plan to use, click <strong>Test Connection</strong>.
            </li>
            <li>
              Wait a few seconds. If it says <strong>Connected</strong>, that printer is ready.
            </li>
            <li>
              If it fails, check that your computer is on the printer network. If it still fails,
              ask IT for help. Do not continue until at least one printer is connected.
            </li>
          </ol>
        </Step>

        <Step
          number={2}
          title="Go to Automated Reconciliation"
          linkTo="/automated"
          linkLabel="Open Automated Reconciliation"
        >
          <p>
            This is the main page you will use every day. Click{' '}
            <strong>Automated Reconciliation</strong> at the top of the screen.
          </p>
        </Step>

        <Step number={3} title="Upload or choose your List A file">
          <ol className="mt-1 list-decimal space-y-2 pl-5">
            <li>
              Under <strong>Step 1 — Select List A</strong>, either:
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>
                  Choose a List A file you already uploaded from the dropdown, or
                </li>
                <li>
                  Click <strong>Upload New List A</strong> and pick your Excel file from your
                  computer.
                </li>
              </ul>
            </li>
            <li>Wait until the green box appears showing the file name and how many rows it found.</li>
            <li>
              If the upload fails, make sure the file is a normal Excel file (.xlsx) and that it has
              an ISBN column. If you are unsure, ask a colleague who prepares List A.
            </li>
          </ol>
        </Step>

        <Step number={4} title="Choose which printers to use">
          <ol className="mt-1 list-decimal space-y-2 pl-5">
            <li>
              Under <strong>Step 2 — Connect to Printer</strong>, tick the printers you want.
            </li>
            <li>You can choose one printer, or two, or all three.</li>
            <li>
              If you want all of them, click <strong>Select All Printers</strong>.
            </li>
          </ol>
        </Step>

        <Step number={5} title="Choose the report date range">
          <ol className="mt-1 list-decimal space-y-2 pl-5">
            <li>
              Under <strong>Step 3 — Report Date Range</strong>, set:
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>
                  <strong>From Date</strong> — the first day you want to include
                </li>
                <li>
                  <strong>To Date</strong> — the last day you want to include
                </li>
              </ul>
            </li>
            <li>
              Example: From 01-Aug-2026 To 26-Aug-2026 means “get everything those printers printed
              between those two dates.”
            </li>
            <li>The From date must be on or before the To date.</li>
            <li>You cannot choose a date in the future — only today or earlier dates are allowed.</li>
          </ol>
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
            <strong>Important:</strong> This date range only controls <em>which jobs are
            downloaded</em>. Later, each book’s own print date in the Excel report comes from the
            printer’s job record — not from today’s date, and not from the day you clicked download.
          </div>
        </Step>

        <Step number={6} title="Download printer data and reconcile">
          <ol className="mt-1 list-decimal space-y-2 pl-5">
            <li>
              Click the big button: <strong>Download Printer Data &amp; Reconcile</strong>.
            </li>
            <li>Wait. The app will connect to each selected printer and download the jobs.</li>
            <li>You will see progress steps (connecting, downloading, matching, and so on).</li>
            <li>
              When it is finished, a popup appears that says{' '}
              <strong>Ready to export your file</strong>.
            </li>
            <li>
              If something fails, read the simple message on screen. Often it means the printer
              could not be reached — check the network and try again, or ask IT.
            </li>
          </ol>
        </Step>

        <Step number={7} title="Export the Normalized Report">
          <ol className="mt-1 list-decimal space-y-2 pl-5">
            <li>
              In the popup, click <strong>Export Normalized Report</strong>.
            </li>
            <li>Or, if you closed the popup, use the same button lower on the page.</li>
            <li>An Excel file will download to your computer. Open it with Excel.</li>
          </ol>
        </Step>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">
            Step 8 — Understand the Excel file
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            The report has several sheets (tabs at the bottom of Excel). Open them one by one:
          </p>

          <div className="mt-4 space-y-4 text-sm leading-relaxed text-slate-600">
            <SheetExplain title="List A ISBNs">
              Every book number from your List A file, in the same order, including duplicates. If
              List A had 87 rows, this sheet has 87 rows.
            </SheetExplain>
            <SheetExplain title="Printer 1 ISBNs / Printer 2 ISBNs / Printer 3 ISBNs">
              One sheet for each printer you selected. Each row is one printed job that had a book
              number in the filename. Columns are:
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>
                  <strong>ISBN</strong> — the book number found in the filename
                </li>
                <li>
                  <strong>Print Date</strong> — the day that job was printed on the printer
                </li>
                <li>
                  <strong>Source Filename</strong> — the original printer filename
                </li>
              </ul>
              The same book number can appear more than once if it was printed more than once.
            </SheetExplain>
            <SheetExplain title="Reconciliation">
              One row for every List A row. Status is:
              <ul className="mt-2 list-disc space-y-1 pl-5">
                <li>
                  <strong>PRESENT</strong> — this book was found on at least one selected printer
                </li>
                <li>
                  <strong>NOT FOUND</strong> — this book was not found in the downloaded printer data
                </li>
              </ul>
              If it is PRESENT, the Print Date column shows when it was printed (or dates, if it
              printed more than once), and the Printer column shows which printer(s) it came from
              (for example Printer 1, or Printer 1, Printer 2 if it was found on more than one).
            </SheetExplain>
            <SheetExplain title="Skipped ISBNs">
              Printer jobs where no book number could be found (for example “CE Adjust”). These are
              not treated as books. They are listed here so nothing is silently ignored.
            </SheetExplain>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">Three different dates (do not mix them)</h2>
          <dl className="mt-3 space-y-3 text-sm leading-relaxed text-slate-600">
            <div>
              <dt className="font-medium text-slate-800">1. Report Date Range</dt>
              <dd>
                The From / To dates you chose. Example: 01-Aug-2026 → 26-Aug-2026.
              </dd>
            </div>
            <div>
              <dt className="font-medium text-slate-800">2. Print Date</dt>
              <dd>
                The date on each printer job for that book. Example: 25-Aug-2026. This is what
                Operations usually cares about for “when was it printed?”
              </dd>
            </div>
            <div>
              <dt className="font-medium text-slate-800">3. Downloaded On</dt>
              <dd>
                The date and time you ran the download on this computer. Example: 27-Aug-2026 11:30
                AM. This is not the print date.
              </dd>
            </div>
          </dl>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">Opening an old run again</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            At the bottom of Automated Reconciliation, use the{' '}
            <strong>Reconciliation History</strong> dropdown. Pick a previous run to see its summary
            and export the report again. You do not need to download from the printers again unless
            you want a new date range or fresh data.
          </p>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">
            Manual Reconciliation (only if needed)
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            Most days you should use <strong>Automated Reconciliation</strong>. Use{' '}
            <Link className="font-medium text-sky-800 underline" to="/">
              Manual Reconciliation
            </Link>{' '}
            only if someone gives you Excel files that were already downloaded from the printers by
            hand, and you need to match those files against List A without connecting to the
            printers.
          </p>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-900">If something goes wrong</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-slate-600">
            <li>
              <strong>Cannot connect to a printer</strong> — Make sure you are on the office
              printer network. Then try Test Connection again. If it still fails, ask IT.
            </li>
            <li>
              <strong>List A will not upload</strong> — Use a normal Excel file (.xlsx) with an ISBN
              column. Do not upload a Word document or a random text file.
            </li>
            <li>
              <strong>No records found</strong> — The date range may have no jobs on that printer.
              Try a wider date range, or confirm printing happened on those days.
            </li>
            <li>
              <strong>Wrong date range</strong> — From date must be earlier than or equal to To
              date. Future dates are not allowed.
            </li>
            <li>
              <strong>Need a password fixed</strong> — Passwords are set by IT on the computer. They
              are never shown on the screen. Ask IT; do not look for a password box in the app.
            </li>
          </ul>
        </section>

        <section className="rounded-lg border border-slate-200 bg-slate-50 p-5">
          <h2 className="text-base font-semibold text-slate-900">Quick checklist</h2>
          <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-slate-700">
            <li>Connect to Printer → Test Connection</li>
            <li>Automated Reconciliation → Upload List A</li>
            <li>Select printers</li>
            <li>Set From date and To date</li>
            <li>Download Printer Data &amp; Reconcile</li>
            <li>When the popup appears → Export Normalized Report</li>
            <li>Open the Excel file and check Reconciliation</li>
          </ol>
          <div className="mt-4">
            <Link
              to="/automated"
              className="inline-flex rounded-md bg-slate-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-700"
            >
              Start Automated Reconciliation
            </Link>
          </div>
        </section>
      </main>
    </AppLayout>
  )
}

function Step({
  number,
  title,
  children,
  linkTo,
  linkLabel,
}: {
  number: number
  title: string
  children: React.ReactNode
  linkTo?: string
  linkLabel?: string
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">
        Step {number} — {title}
      </h2>
      <div className="mt-2 text-sm leading-relaxed text-slate-600">{children}</div>
      {linkTo && linkLabel ? (
        <div className="mt-4">
          <Link
            to={linkTo}
            className="inline-flex rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
          >
            {linkLabel}
          </Link>
        </div>
      ) : null}
    </section>
  )
}

function SheetExplain({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-slate-100 bg-slate-50 px-3 py-3">
      <div className="font-medium text-slate-800">{title}</div>
      <div className="mt-1">{children}</div>
    </div>
  )
}
