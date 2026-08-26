# Operations Installation Guide
# Printing Reconciliation

## What this application does

Printing Reconciliation helps you compare your List A ISBN file with jobs that were printed on the office printers. It shows which List A items are present on the printer and which are not found.

---

## 1. How to install

1. Get the installer file from IT: **Printing-Reconciliation-Setup-1.0.0.exe**
2. Double-click the installer.
3. Follow the on-screen steps (Next → Install → Finish).
4. You do **not** need administrator rights for a normal per-user install.

If Windows shows a SmartScreen warning (“Windows protected your PC”), ask IT. This can happen when the installer is not code-signed yet. IT can choose **More info → Run anyway** if they trust the file.

---

## 2. How to open the application

After installation you will see:

- A **Desktop** shortcut named **Printing Reconciliation**
- A **Start Menu** entry with the same name

Double-click the Desktop shortcut. The application opens by itself. You do not need to start anything else.

---

## 3. How to check printer connection

1. Open **Printers** (or Printer Configuration) in the app.
2. For Printer 1, Printer 2, and Printer 3 you will see connection status.
3. Click **Test Connection** for each printer you use.

**Connected** means the app can reach that printer on the office network.

**Not Connected** means the app cannot reach the printer right now.

---

## 4. How to upload List A

1. Go to the main / Automated Reconciliation screen.
2. Choose **Upload List A** (or the List A upload control).
3. Select your Excel / CSV List A file.
4. Wait until the upload finishes successfully.

---

## 5. How to select printer and date range

1. Select the printer(s) you want to check (usually **Printer 1**).
2. Choose the **start date** and **end date** for the printer jobs.
3. Confirm the dates match the period you want to reconcile.

Your computer must be on the **office printer network** for printer download to work.

---

## 6. How to run reconciliation

1. After List A is uploaded and the printer / dates are selected, start the reconciliation run.
2. Wait until the run shows as completed.
3. Review the summary on screen.

---

## 7. How to export the normalized report

1. Click **Export Normalized Report**.
2. Save the Excel file to a folder you can find (for example Desktop or Documents).
3. Open the file in Excel.

The normalized report has four sheets:

| Sheet | Meaning |
|-------|---------|
| **List A ISBNs** | Every ISBN from your List A file (duplicates kept) |
| **Printer ISBNs** | Every ISBN found on the printer (duplicates kept), with source filename |
| **Reconciliation** | Each List A ISBN occurrence and whether it was found on the printer |
| **Skipped ISBNs** | Printer jobs where no ISBN could be read from the filename |

You can also use **Export Detailed Report** for the fuller audit workbook.

---

## 8. What PRESENT means

**PRESENT** means that List A ISBN was found at least once in the printer data for the selected date range.

---

## 9. What NOT FOUND means

**NOT FOUND** means that List A ISBN was **not** found in the printer data for the selected date range.

---

## 10. What Skipped ISBNs means

Some printer jobs do not contain a readable ISBN in the filename (for example “CE Adjust” or a title-only PDF name).

Those jobs are listed on **Skipped ISBNs**. They are real printer jobs, but they are not included on the Printer ISBNs sheet because no ISBN could be extracted.

---

## 11. What to do if a printer is not connected

1. Confirm your PC is on the office network (same network as the printers).
2. Ask a colleague if the printers are powered on and working.
3. Open the app → Printers → **Test Connection**.
4. If it still fails, contact IT. Tell them which printer number failed (1, 2, or 3).

Friendly message you may see:

> Unable to connect to Printer 1.  
> Please check that your computer is connected to the office printer network.

---

## 12. Who to contact for technical problems

Contact **IT support** if:

- The application will not open
- You see “Printing Reconciliation could not start”
- Printer tests keep failing while others succeed
- Reports will not export

IT can find application logs under your Windows user profile application data folder for **Printing Reconciliation**.

---

## Closing the application

Use the normal window **X** (close) button. The application shuts down completely. You can open it again later from the Desktop shortcut.
