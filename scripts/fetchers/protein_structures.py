"""Refresh the protein-structures frontier from the RCSB PDB growth statistics page (CC0 1.0).

The page has one table: year, total entries available, and structures released that year.
The dataset copy (released-per-year.csv) is rebuilt from it, and the frontier's cumulative
observations are regenerated from that copy.
"""
import csv
import io
import re
from html.parser import HTMLParser

from . import common

FRONTIER = "data/frontiers/biology/protein-structures.yaml"
DATASET = "data/datasets/pdb-released-structures"
CSV_PATH = f"{DATASET}/released-per-year.csv"
SOURCE_URL = "https://bioinformatics.rcsb.org/stats/growth/growth-released-structures"
SOURCE_ID = "rcsb-growth-stats"
SERIES = "pdb-cumulative"
FIRST_YEAR = 1976
COLUMNS = ["year", "released_in_year", "cumulative_total"]
MIN_YEARS = 40  # the table has run since 1976; a page with fewer rows is a broken read
YEAR_RE = re.compile(r"\d{4}")
COUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")
OBSERVATION_RE = re.compile(
    r"(?:- date: '\d{4}'\n  series: " + SERIES + r"\n  value: \d+\n  source: " + SOURCE_ID + r"\n)*")


class _TableRows(HTMLParser):
    """Collects the text of every table row, cell by cell."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _count(text):
    if not COUNT_RE.fullmatch(text):
        raise common.SourceError(f"could not read a count from {text!r}")
    return int(text.replace(",", ""))


def parse_table(html):
    """Return (year, released_in_year, cumulative_total) tuples, oldest first."""
    parser = _TableRows()
    parser.feed(html)

    columns = None
    for row in parser.rows:
        lowered = [c.lower() for c in row]
        if len(row) == 3 and any("total" in c for c in lowered) and any("released" in c for c in lowered):
            found = {}
            for i, c in enumerate(lowered):
                if "released" in c:
                    found["released"] = i
                elif "total" in c:
                    found["total"] = i
                elif "year" in c:
                    found["year"] = i
            if len(found) != 3:
                raise common.SourceError(f"the table headings changed: {row}")
            columns = found
            break
    if columns is None:
        raise common.SourceError("no table with Year, Total and Released headings was found")

    by_year = {}
    for row in parser.rows:
        if len(row) != 3 or not YEAR_RE.fullmatch(row[columns["year"]]):
            continue
        year = int(row[columns["year"]])
        if year in by_year:
            raise common.SourceError(f"year {year} appears twice in the table")
        by_year[year] = (_count(row[columns["released"]]), _count(row[columns["total"]]))

    years = sorted(by_year)
    if not years or years[0] != FIRST_YEAR or years != list(range(FIRST_YEAR, years[-1] + 1)):
        raise common.SourceError(f"years are not consecutive from {FIRST_YEAR}: {years[:3]} ... {years[-3:]}")
    if len(years) < MIN_YEARS:
        raise common.SourceError(f"only {len(years)} years in the table")

    rows, running = [], 0
    for year in years:
        released, total = by_year[year]
        running += released
        if running != total:
            raise common.SourceError(f"{year}: released counts add up to {running:,}, the page's total is {total:,}")
        rows.append((year, released, total))
    return rows


def _read_csv():
    text = (common.ROOT / CSV_PATH).read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != COLUMNS:
        raise common.SourceError(f"{CSV_PATH} has unexpected columns {reader.fieldnames}")
    return [(int(r["year"]), int(r["released_in_year"]), int(r["cumulative_total"])) for r in reader]


def _csv_text(rows):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return out.getvalue()


def _frontier_text(rows):
    """Return the frontier file with its observations regenerated from the cumulative totals."""
    text = (common.ROOT / FRONTIER).read_text(encoding="utf-8")
    marker = "\nobservations:\n"
    if text.count(marker) != 1:
        raise common.SourceError("no single observations block found in the frontier file")
    head, tail = text.split(marker)
    if not OBSERVATION_RE.fullmatch(tail):
        raise common.SourceError("the observations block has entries other than the pdb-cumulative series")
    lines = ["observations:"]
    for year, _, total in rows:
        lines += [f"- date: '{year}'", f"  series: {SERIES}", f"  value: {total}", f"  source: {SOURCE_ID}"]
    return head + "\n" + "\n".join(lines) + "\n"


def _set_row(text, label, value):
    """Replace one row of the README's two-column table without touching the lines around it."""
    pattern = re.compile(r"(?m)^\|\s*" + re.escape(label) + r"\s*\|[^\n]*$")
    new, n = pattern.subn(lambda m: f"| {label} | {value} |", text, count=1)
    if n != 1:
        raise common.SourceError(f"no '{label}' row in the dataset README")
    return new


def _update_readme(csv_bytes, last_year):
    path = common.ROOT / DATASET / "README.md"
    text = path.read_text(encoding="utf-8")
    text = _set_row(text, "Retrieved", common.today())
    text = _set_row(text, "Coverage", f"Years 1976 to {last_year}. A row is added when RCSB publishes a new year.")
    text = _set_row(text, "Page as read", "Read by the refresh fetcher from the page above. Columns are matched by their headings.")
    text = _set_row(text, "released-per-year.csv SHA-256", common.sha256(csv_bytes))
    path.write_text(text, encoding="utf-8")


def fetch():
    html = common.get(SOURCE_URL).decode("utf-8", errors="replace")
    rows = parse_table(html)

    old = _read_csv()
    new_by_year = {year: (released, total) for year, released, total in rows}
    missing = [y for y, _, _ in old if y not in new_by_year]
    if missing:
        raise common.SourceError(f"years on file are missing from the page: {missing[:5]}")
    if len(rows) < len(old):
        raise common.SourceError(f"the page has {len(rows)} years, fewer than the {len(old)} on file")

    old_by_year = {year: (released, total) for year, released, total in old}
    changes = []
    for year, released, total in rows:
        if year not in old_by_year:
            changes.append(f"{year}: {released:,} structures released, {total:,} in the archive")
        elif old_by_year[year] != (released, total):
            o_rel, o_tot = old_by_year[year]
            changes.append(f"{year} revised: released {o_rel:,} -> {released:,}, total {o_tot:,} -> {total:,}")

    csv_text = _csv_text(rows)
    csv_changed = common.write_if_changed(CSV_PATH, csv_text)
    frontier_changed = common.write_if_changed(FRONTIER, _frontier_text(rows))
    if csv_changed:
        _update_readme(csv_text.encode("utf-8"), rows[-1][0])
    if not csv_changed and not frontier_changed:
        return []
    return changes or ["Growth table rewritten (no value changes)"]
