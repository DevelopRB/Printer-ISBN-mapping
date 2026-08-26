# Printer Job Log API — Phase 2C Findings

**Status:** Confirmed against live printers (not guessed).  
**Primary probe:** Printer 1 — `https://192.168.2.7:30092`  
**Also verified same protocol:** Printer 2 and Printer 3.

Passwords, cookies, nonces, and session secrets are shown as `<REDACTED>`.

---

## Summary (confirmed)

| Item | Finding |
|------|---------|
| Authentication | **HTTP Digest** (`WWW-Authenticate: Digest ...`). **HTTP Basic also accepted** by these devices (both returned HTTP 200 in probes). Prefer Digest to match the challenge. |
| Session cookies | **Not required** for joblog access when using Digest/Basic per-request auth. No `Set-Cookie` observed on successful joblog GETs. |
| CSRF | **None observed** on `JobLogForm`. |
| Endpoint | `/goform/joblog.cgi` |
| Primary UI action | **POST** `application/x-www-form-urlencoded` to `/goform/joblog.cgi` |
| Alternate | **GET** `/goform/joblog.cgi?rs=YYYYMMDD&re=YYYYMMDD` also filters by date |
| HTML list response | `text/html` page embedding JS array `joblog[i] = "…\t…"` |
| Native download | POST with `cmd=dl` → `application/octet-stream` TSV attachment |
| Client CSV | Browser `dlcsv()` builds CSV **in the browser** from `csvtxt` — not a server export |
| Filename field | Column ID **`4010`** (filename / document name) |
| Date field | Column IDs **`1000,1001,1002`** = year / month / day of job reception (values like `26`,`08`,`24`) |
| Date-range params | Form fields **`rs`** and **`re`** (digits only, **`YYYYMMDD`**) |
| Index pagination | Form fields **`start`** and **`end`** = **job-log index numbers**, not calendar dates |

---

## PRINTER 1

Base URL: `https://192.168.2.7:30092`  
Job log: `https://192.168.2.7:30092/goform/joblog.cgi`

### Authentication

Unauthenticated GET `/goform/joblog.cgi` returns **401**:

```
WWW-Authenticate: Digest realm="By Password", domain="…", qop="auth",
  nonce="<REDACTED>", opaque="<REDACTED>", algorithm="MD5", stale="FALSE"
```

Username from env: `PRINTER_1_USERNAME` (default `admin`)  
Password from env: `PRINTER_1_PASSWORD` = `<REDACTED>`

No form-login cookie session was required for joblog when Digest/Basic credentials were supplied on each request.

### Default list request (browser initial load)

```
GET /goform/joblog.cgi
Authorization: Digest username="admin", realm="By Password", nonce="<REDACTED>", … <REDACTED>
```

Response: `200 text/html`  
Contains JS variables such as:

- `logtotal=<N>`
- `logstart=<N>`
- `logend=<N>`
- `joblog[i] = "<tab-separated fields>"`

Default window observed: last **100** jobs (`logend - logstart + 1 ≈ 100`).

### Browser form used for navigation / filter / download

From page HTML (`name="JobLogForm"`):

```
POST /goform/joblog.cgi
Content-Type: application/x-www-form-urlencoded
```

Parameters (names confirmed from HTML + `onJobLog()` JS):

| Parameter | Role |
|-----------|------|
| `cmd` | `""` = view/list; `"dl"` = download attachment |
| `clm` | Comma-separated column IDs to return (includes `4010`, date IDs, etc.) |
| `viw` | View flag (often empty; `viw=A` appears as a link) |
| `start` | Job-log **index** start (pagination), or empty when using dates |
| `end` | Job-log **index** end (pagination), or empty when using dates |
| `rs` | Date-range start, **digits only** `YYYYMMDD` |
| `re` | Date-range end, **digits only** `YYYYMMDD` |
| `clmmode` | Observed default `"0"` |

### Date-range parameters (confirmed by comparing requests)

UI function `onJumpWithDate()`:

1. Reads text inputs `rs` / `re`
2. Strips non-digits: `value.replace(/\D/g, "")`
3. Calls `onJobLog("","","","","",rs,re)` → POST with empty `start`/`end` and filled `rs`/`re`

**Working format (confirmed):**

- `rs=20260801`, `re=20260826` → **2269** jobs (Printer 1)
- `rs=20260810`, `re=20260815` → **584** jobs (Printer 1)

**Not reliable:**

- `rs=260801`, `re=260826` (YYMMDD) → did **not** apply the intended filter (fell back to default ~100-row window)

So backend date encoding must be **`YYYYMMDD`**.

GET alternative also confirmed:

```
GET /goform/joblog.cgi?rs=20260810&re=20260815
```

→ same filtered job count as the POST date filter.

### Column map (`clm`) — from `onJobLog()` on the printer page

Relevant confirmed mappings:

| Index in `clm` list | Column ID | Meaning (from JS comments / data) |
|---------------------|-----------|-----------------------------------|
| 0 | `1122` | Job number |
| 1 | `4001` | Mode |
| 2 | `4009` | User name |
| 3 | `4010` | **Filename** |
| 4 | `4005` | Result |
| 9–11 | `1000,1001,1002` | **Reception date** YY / MM / DD |
| 12–14 | `1003,1004,1005` | Reception time HH / MM / SS |
| 15–20 | `1285`…`1290` | Print start date/time parts |
| 21–26 | `1006`…`1011` | Reception end date/time parts |

Full `clm` string used by the UI (sanitized copy of page JS):

```
1122,4001,4009,4010,4005,1630,1034,1091,2003,
1000,1001,1002,1003,1004,1005,
1285,1286,1287,1288,1289,1290,
1006,1007,1008,1009,1010,1011,
1041,1045,1022,4005,1047,2025,2106,
1271,1272,1273,1274,1275,1401,
1610,1611,1612,1613,1614,1615,1616,
1617,1618,1619,1620,1276,1277,1278,1279,1621
```

### Filename / `4010`

The joblog response **does** include the same style of values previously seen in Excel column `4010`, e.g.:

```
Pub_9788121213790 F2 HB  vol 2 (2)_Pharma..pdf
Pub_9789373168326_HB_ BOOK_F4_QC_Pharma..pdf
```

Map to application field: **`source_filename`** (column ID `4010`).

Do **not** treat `(2)`, `(2 COPIES)`, `F2`, etc. as quantity.

### Printer date

Use reception date parts **`1000`/`1001`/`1002`** (YY/MM/DD) as `printer_date`.  
Example from filtered data: `26`,`08`,`01` → `2026-08-01` (assume century 2000+ for two-digit year).

### Export / download

1. **Server download (preferred for automation)**  
   Browser calls `onJobLogDL()` → `onJobLog("dl","","",logstart,logend,"","")`

   Confirmed request:

   ```
   POST /goform/joblog.cgi
   Content-Type: application/x-www-form-urlencoded

   cmd=dl
   clm=<column id list>
   viw=
   start=<index or empty>
   end=<index or empty>
   rs=<YYYYMMDD or empty>
   re=<YYYYMMDD or empty>
   clmmode=0
   ```

   Confirmed response:

   - `Content-Type: application/octet-stream`
   - `Content-Disposition: attachment; filename="<start>-<end>.txt"`
   - Body: **tab-separated** text
   - Row 1: header of column IDs (`0`, `1122`, `4001`, `4009`, `4010`, …)
   - Following rows: one job per line
   - In download rows, column `4010` is at header position of `4010` (observed index **4** because leading log-index column `0` is present)

   Date-range download example:

   ```
   cmd=dl&rs=20260801&re=20260826&start=&end=&…
   → filename="22508-24776.txt", ~2270 lines (header + jobs)
   ```

2. **Browser “Convert CSV”**  
   `dlcsv()` opens a popup and writes `csvtxt` built client-side. **Not** a server CSV endpoint — do not rely on this for backend automation.

### Pagination / sorting

- Pagination uses **`start`/`end` job indices** in steps of ~100 (`onJumpPrevious` / `onJumpNext` / jump selector).
- Date filter uses **`rs`/`re`** and leaves `start`/`end` empty.
- No separate sort parameter observed on the form.

### Example sanitized POST (date filter + list HTML)

```
POST /goform/joblog.cgi
Authorization: Digest … <REDACTED>
Content-Type: application/x-www-form-urlencoded

cmd=
clm=1122,4001,4009,4010,…,1621
viw=
start=
end=
rs=20260801
re=20260826
clmmode=0
```

Response: `200 text/html` with embedded `joblog[i]` entries.

### Example sanitized POST (download)

```
POST /goform/joblog.cgi
Authorization: Digest … <REDACTED>
Content-Type: application/x-www-form-urlencoded

cmd=dl
clm=1122,4001,4009,4010,…,1621
viw=
start=
end=
rs=20260801
re=20260826
clmmode=0
```

Response: `200 application/octet-stream` attachment TSV.

---

## Printer 2 / Printer 3

Same `/goform/joblog.cgi` protocol confirmed:

| Slot | Base | JobLogForm | onJobLog | rs/re | 4010 | Date POST jobs (20260810–20260815) |
|------|------|------------|----------|-------|------|-------------------------------------|
| 2 | `https://192.168.2.218:30092` | yes | yes | yes | yes | 495 |
| 3 | `http://192.168.2.176:30091` | yes | yes | yes | yes | 1132 |

Reusable single adapter is appropriate; only protocol/host/port differ.

---

## Backend implications (Phase 2D+)

1. Authenticate with **Digest** (Basic as fallback if needed).
2. Prefer **`cmd=dl`** download for structured TSV over HTML scraping.
3. Encode dates as **`YYYYMMDD`** in `rs` / `re`.
4. Parse TSV header by column ID; map `4010` → filename, `1000/1001/1002` → date.
5. Reuse existing ISBN extractor on filename; do not invent quantity logic.
6. Do **not** hard-code session cookies.

---

## Probe artifacts

Local (gitignored under `backend/data/`):

- `backend/data/joblog_probe/00_summary.json`
- `backend/data/joblog_probe/27_deep_probe_results.json`
- `backend/data/joblog_probe/28_printer23_compare.json`
- `backend/scripts/probe_joblog_*.py`

---

## Phase 2C checklist

1. Authentication method — **Digest (Basic also works)**
2. HTTP method — **POST** (GET works for list/date query)
3. Request parameters — **cmd, clm, viw, start, end, rs, re, clmmode**
4. Date-range parameters — **rs / re as YYYYMMDD**
5. Export/download — **cmd=dl → octet-stream TSV**
6. Response format — **HTML+JS list** or **TSV download**
7. Date field — **1000/1001/1002**
8. Filename field — **4010**
9. Sanitized docs — **this file**
10. Working backend test — **debug endpoint + adapter probe**
