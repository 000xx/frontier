"""Check the genome sequencing cost frontier against NHGRI's Sequencing Cost Data Table.

The frontier's observations were copied from a DataHub CSV of this table. This fetcher reads
NHGRI's own workbook, linked from the NHGRI fact sheet, and then:
- compares every existing observation with the workbook and reports any mismatch. It never
  changes an existing value, so the owner decides what to do about a mismatch;
- appends observations for months after the last date the frontier already holds.
"""
import datetime as dt
import io
import math
import re
from urllib.parse import urljoin

from . import common

FRONTIER = "data/frontiers/biology/genome-sequencing-cost.yaml"
FACT_SHEET = "https://www.genome.gov/about-genomics/fact-sheets/DNA-Sequencing-Costs-Data"
SOURCE_ID = "nhgri-table"
SERIES_HEADERS = {"cost-per-genome": "genome", "cost-per-megabase": "megabase"}
TOLERANCE = 0.0005    # the frontier keeps three decimal places
MIN_ROW_SHARE = 0.9   # fail if the workbook holds fewer months than this share of the frontier
OBS_LINE = re.compile(r"^- \{date: '(\d{4}-\d{2})', value: ([0-9.eE+-]+), series: ([a-z-]+), source: ([a-z-]+)")
DATE_FORMATS = ("%Y-%m-%d", "%Y-%m", "%m/%d/%Y", "%b-%y", "%b-%Y", "%b %Y", "%B %Y")


def workbook_url():
    """Find the one workbook linked from the NHGRI fact sheet."""
    html = common.get(FACT_SHEET).decode("utf-8", errors="replace")
    links = []
    for href in re.findall(r"""href=["']([^"']+\.xlsx?)["']""", html, flags=re.IGNORECASE):
        url = urljoin(FACT_SHEET, href.replace("&amp;", "&"))
        if url not in links:
            links.append(url)
    if len(links) != 1:
        raise common.SourceError(f"expected one workbook link on the fact sheet, found {len(links)}: {links}")
    return links[0]


def read_sheets(data, url):
    """Return every sheet as a list of rows of cell values."""
    if url.lower().endswith(".xls"):
        import xlrd
        try:
            book = xlrd.open_workbook(file_contents=data)
        except Exception as exc:  # noqa: BLE001
            raise common.SourceError(f"could not open the .xls workbook: {exc}") from exc
        sheets = []
        for sheet in book.sheets():
            rows = []
            for r in range(sheet.nrows):
                cells = []
                for c in range(sheet.ncols):
                    cell = sheet.cell(r, c)
                    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        cells.append(None)
                    elif cell.ctype == xlrd.XL_CELL_DATE:
                        cells.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
                    else:
                        cells.append(cell.value)
                rows.append(cells)
            sheets.append(rows)
        return sheets

    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise common.SourceError(f"could not open the .xlsx workbook: {exc}") from exc
    return [[list(row) for row in ws.iter_rows(values_only=True)] for ws in wb.worksheets]


def find_table(sheets):
    """Find the header row that names the date, genome and megabase columns."""
    for rows in sheets:
        for i, row in enumerate(rows[:30]):
            cols = {}
            for c, cell in enumerate(row):
                text = str(cell or "").lower()
                if "date" in text and "date" not in cols:
                    cols["date"] = c
                for series, word in SERIES_HEADERS.items():
                    if word in text and series not in cols:
                        cols[series] = c
            if {"date", *SERIES_HEADERS} <= cols.keys():
                return rows, i, cols
    preview = []
    for n, rows in enumerate(sheets):
        for row in rows[:12]:
            cells = [str(c) for c in row if c not in (None, "")]
            if cells:
                preview.append(f"sheet {n}: " + " | ".join(cells)[:200])
    raise common.SourceError("no table with date, genome and megabase columns was found in the workbook; "
                             "first rows: " + " ;; ".join(preview[:30]))


def month_of(cell):
    """Return the 'YYYY-MM' month of a date cell. Raise if the cell is not a recognisable date."""
    if isinstance(cell, (dt.datetime, dt.date)):
        return cell.strftime("%Y-%m")
    text = str(cell).strip()
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).strftime("%Y-%m")
        except ValueError:
            pass
    raise common.SourceError(f"could not read the date {cell!r}")


def number_of(cell, where):
    """Return a finite float, None for a blank cell, or raise for anything else."""
    if cell is None or (isinstance(cell, str) and not cell.strip()):
        return None
    if isinstance(cell, bool):
        raise common.SourceError(f"{where}: expected a number, found {cell!r}")
    if isinstance(cell, (int, float)):
        value = float(cell)
    else:
        try:
            value = float(str(cell).replace("$", "").replace(",", "").strip())
        except ValueError as exc:
            raise common.SourceError(f"{where}: expected a number, found {cell!r}") from exc
    if not math.isfinite(value):
        raise common.SourceError(f"{where}: value is not finite: {cell!r}")
    return value


def parse_table(rows, header_index, cols):
    """Return {series: {'YYYY-MM': value}} from the rows under the header."""
    table = {series: {} for series in SERIES_HEADERS}
    for row_number, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        def cell(c):
            return row[c] if c < len(row) else None
        values = {series: cell(cols[series]) for series in SERIES_HEADERS}
        date_cell = cell(cols["date"])
        if date_cell in (None, "") and all(v in (None, "") for v in values.values()):
            continue
        if date_cell in (None, ""):
            raise common.SourceError(f"row {row_number} has values but no date")
        month = month_of(date_cell)
        for series, raw in values.items():
            value = number_of(raw, f"row {row_number} {series}")
            if value is None:
                continue
            if month in table[series]:
                raise common.SourceError(f"two rows for {month} in {series}")
            table[series][month] = value
    return table


def num_text(value):
    text = repr(float(value))
    if "e" in text or "E" in text:
        text = format(float(value), "f")
    return text


def write_additions(additions):
    """Append new observation lines after the last existing line of each series."""
    path = common.ROOT / FRONTIER
    lines = path.read_text(encoding="utf-8").split("\n")
    last_line = {}
    for i, line in enumerate(lines):
        match = OBS_LINE.match(line)
        if match:
            last_line[match.group(3)] = i
    inserts = {}
    for series, items in additions.items():
        if not items:
            continue
        if series not in last_line:
            raise common.SourceError(f"no observations for {series} in the frontier file")
        inserts[last_line[series]] = [
            f"- {{date: '{month}', value: {num_text(value)}, series: {series}, source: {SOURCE_ID}}}"
            for month, value in items
        ]
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        out.extend(inserts.get(i, []))
    path.write_text("\n".join(out), encoding="utf-8")


def fetch():
    url = workbook_url()
    sheets = read_sheets(common.get(url), url)
    rows, header_index, cols = find_table(sheets)
    nhgri = parse_table(rows, header_index, cols)

    existing = {}
    for obs in common.load(FRONTIER).get("observations") or []:
        existing[(obs["series"], str(obs["date"])[:7])] = float(obs["value"])

    for series in SERIES_HEADERS:
        have = sum(1 for s, _ in existing if s == series)
        got = len(nhgri[series])
        if have and got < MIN_ROW_SHARE * have:
            raise common.SourceError(f"{series}: the workbook has {got} months, the frontier has {have}")

    messages = []
    mismatches = 0
    missing = 0
    for (series, month), old in sorted(existing.items()):
        new = nhgri[series].get(month)
        if new is None:
            missing += 1
            messages.append(f"Not in NHGRI workbook: {month} {series} (frontier {old:,.3f}; not changed)")
        elif abs(old - new) > TOLERANCE:
            mismatches += 1
            messages.append(f"Mismatch {month} {series}: frontier {old:,.3f}, NHGRI {new:,.3f} (not changed)")

    last_month = {}
    for series, month in existing:
        last_month[series] = max(last_month.get(series, ""), month)
    additions = {series: [] for series in SERIES_HEADERS}
    for series in SERIES_HEADERS:
        for month in sorted(nhgri[series]):
            if (series, month) in existing:
                continue
            if month > last_month.get(series, ""):
                additions[series].append((month, nhgri[series][month]))
                messages.append(f"New {series} {month}: {nhgri[series][month]:,.3f} (NHGRI)")
            else:
                messages.append(f"Not added, before the frontier's last date: {month} {series}")

    newest = {s: max(nhgri[s]) for s in SERIES_HEADERS if nhgri[s]}
    print(f"NHGRI workbook {url}: {len(rows)} rows, newest months {newest}; "
          f"{len(existing)} existing observations, {mismatches} mismatches, {missing} missing")

    if any(additions.values()):
        write_additions(additions)
    return messages
