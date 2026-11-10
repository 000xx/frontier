"""Refresh the largest-known-prime frontier from the GIMPS table of Mersenne primes (mersenne.org/primes/).

Reads the table, works out the records in the computer era (1952 on: a prime is a record when its
digit count beats every prime discovered before it), and adds only records whose exponent is not
already in the frontier file. Existing entries are never rewritten. Only facts from the table are
stored, each with a link, because GIMPS owns its data (see the frontier's source notes).
"""
import datetime as dt
import re
from html.parser import HTMLParser

import yaml

from . import common

FRONTIER = "data/frontiers/mathematics/largest-known-prime.yaml"
SOURCE_URL = "https://www.mersenne.org/primes/"
COMPUTER_ERA_START = 1952
MIN_ROWS = 40  # the table has about 52 rows; fewer means the page changed or was cut short


class _TableParser(HTMLParser):
    """Collects every <table> as a list of rows, each a list of cell text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._table = self._row = self._cell = None

    def _end_cell(self):
        if self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None

    def _end_row(self):
        self._end_cell()
        if self._row is not None:
            self._table.append(self._row)
            self._row = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._end_row()
            self._row = []
        elif tag in ("td", "th") and self._table is not None:
            self._end_cell()
            if self._row is None:
                self._row = []
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._end_cell()
        elif tag == "tr":
            self._end_row()
        elif tag == "table" and self._table is not None:
            self._end_row()
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _columns(header):
    cols = {}
    for i, cell in enumerate(header):
        name = cell.lower()
        if name.startswith("rank") and "rank" not in cols:
            cols["rank"] = i
        elif "exponent" in name:
            cols["exp"] = i
        elif name.startswith("digits"):
            cols["digits"] = i
        elif "date" in name:
            cols["date"] = i
        elif name.startswith("discoverer"):
            cols["holder"] = i
    return cols if {"exp", "digits", "date", "holder"} <= cols.keys() else None


def _int(text, what):
    cleaned = text.replace(",", "").rstrip("*")
    if not re.fullmatch(r"\d+", cleaned):
        raise common.SourceError(f"could not read the {what} from {text!r}")
    return int(cleaned)


def _date(text):
    """Return the discovery date, or None for dates before the computer era (out of scope)."""
    if not re.match(r"^\d{4}", text) or int(text[:4]) < COMPUTER_ERA_START:
        return None
    if not re.fullmatch(r"\d{4} [A-Za-z]{3} \d{1,2}", text):
        raise common.SourceError(f"could not read the discovery date from {text!r}")
    return dt.datetime.strptime(text, "%Y %b %d").date()


def _rows(raw):
    parser = _TableParser()
    parser.feed(raw)
    parser.close()
    for table in parser.tables:
        for h, header in enumerate(table):
            cols = _columns(header)
            if cols:
                break
        else:
            continue
        out = []
        for cells in table[h + 1:]:
            if len(cells) <= max(cols.values()) or not re.fullmatch(r"\d[\d,]*\*?", cells[cols["exp"]]):
                continue
            holder = cells[cols["holder"]]
            if not holder:
                raise common.SourceError("a row of the GIMPS table has no discoverer")
            out.append({
                "exp": _int(cells[cols["exp"]], "exponent"),
                "digits": _int(cells[cols["digits"]], "digit count"),
                "date": _date(cells[cols["date"]]),
                "holder": holder,
                "provisional": "*" in (cells[cols["rank"]] if "rank" in cols else ""),
            })
        return out
    print("DEBUG tables", len(parser.tables), "table tags", raw.lower().count("<table"), "tr", raw.lower().count("<tr"))
    for t in parser.tables[:5]:
        print("DEBUG table first rows", t[:2])
    i = raw.find("Digits")
    print("DEBUG context", repr(raw[max(0, i - 900):i + 300]) if i >= 0 else "no 'Digits' in page")
    raise common.SourceError("the GIMPS table was not found (no header with exponent, digits, date and discoverer)")


def _records(rows):
    """Rows whose digit count beats every earlier discovery, in the computer era."""
    best, out = 0, []
    for r in sorted((r for r in rows if r["date"]), key=lambda r: (r["date"], r["digits"])):
        if r["digits"] > best:
            out.append(r)
            best = r["digits"]
    return out


def _yaml_str(text):
    return "'" + text.replace("'", "''") + "'"


def fetch():
    rows = _rows(common.get(SOURCE_URL).decode("utf-8", "replace"))
    if len(rows) < MIN_ROWS:
        raise common.SourceError(f"the GIMPS table had {len(rows)} rows, expected at least {MIN_ROWS}")

    data = common.load(FRONTIER)
    existing = set()
    for rec in data["records"]:
        match = re.search(r"p = (\d+)$", rec["conditions"])
        if not match:
            raise RuntimeError(f"no exponent in conditions {rec['conditions']!r}")
        existing.add(int(match.group(1)))

    table_exps = {r["exp"] for r in rows}
    if existing - table_exps:
        raise common.SourceError(f"existing records missing from the table: {sorted(existing - table_exps)}")
    records = _records(rows)
    if not existing <= {r["exp"] for r in records}:
        raise common.SourceError("the record rule does not reproduce the existing records; the table may have changed")

    new = [r for r in records if r["exp"] not in existing]
    if not new:
        return []

    blocks, messages = [], []
    for r in new:
        note = ("Added by the automatic refresh from the GIMPS table, which gives the discovery date. "
                "No GIMPS verification statement was read, so the status is claimed.")
        if r["provisional"]:
            note += " GIMPS marks the ranking as provisional."
        blocks.append(
            f"- date: '{r['date'].isoformat()}'\n"
            f"  value: {r['digits']}\n"
            f"  holder: {_yaml_str(r['holder'])}\n"
            f"  conditions: {_yaml_str('2^p − 1, p = ' + str(r['exp']))}\n"
            "  status: claimed\n"
            "  source: gimps-primes\n"
            f"  url: {SOURCE_URL}\n"
            f"  note: {_yaml_str(note)}\n"
        )
        messages.append(f"{r['date'].year}: 2^{r['exp']} − 1 has {r['digits']:,} digits "
                        f"({r['holder']}, {r['date'].isoformat()}), added as a claimed record")

    text = (common.ROOT / FRONTIER).read_text(encoding="utf-8")
    new_text, n = re.subn(r"(?m)^events:", "".join(blocks) + "events:", text, count=1)
    if n != 1:
        raise RuntimeError("could not find the events block in the frontier file")
    common.write_if_changed(FRONTIER, new_text)
    return messages
