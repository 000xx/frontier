"""Refresh the confirmed exoplanets frontier from the NASA Exoplanet Archive TAP service.

Reads the pscomppars table counted by discovery year. Only counts are kept, so no dataset
copy is written; the archive's acknowledgement and citation wording is in the frontier's
sources. The yearly rows, their running total and the dated total are updated in place
in the observations block. Other lines of the frontier file are left as they are.
"""
import csv
import io
import re

from . import common

FRONTIER = "data/frontiers/astronomy/exoplanets.yaml"
TAP_URL = ("https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query="
           "select+disc_year,count(*)+from+pscomppars+group+by+disc_year+order+by+disc_year&format=csv")
SOURCE = "exoplanet-archive-tap"
TOTAL = "confirmed-planets"
PER_YEAR = "planets-discovered-per-year"
CUMULATIVE = "cumulative-planets-by-year"
TOTAL_NOTE = "Sum of the pscomppars rows by discovery year from the TAP service, on the date it was read."
SHARP_DROP = 0.95  # the total may not fall below this share of the stored total

BLOCK_HEAD = re.compile(r"^- date: '([^']*)'$")


def parse_counts(raw):
    """Return {discovery year: planet count} from the TAP CSV. Raises SourceError on anything odd."""
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8"))))
    except UnicodeDecodeError as exc:
        raise common.SourceError("TAP response is not UTF-8 text") from exc
    if not rows or len(rows[0]) != 2 or rows[0][0].strip().lower() != "disc_year" \
            or "count" not in rows[0][1].lower():
        raise common.SourceError(f"TAP header changed: {rows[0] if rows else 'empty response'}")
    last_year = int(common.today()[:4]) + 1
    counts = {}
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != 2:
            raise common.SourceError(f"TAP row has {len(row)} columns: {row}")
        try:
            year, count = int(row[0]), int(row[1])
        except ValueError as exc:
            raise common.SourceError(f"could not parse TAP row {row}") from exc
        if year in counts or count < 1 or not 1500 <= year <= last_year:
            raise common.SourceError(f"unexpected TAP row {row}")
        counts[year] = count
    if not counts:
        raise common.SourceError("TAP returned no rows")
    return counts


def locate_observations(lines):
    """Return one dict per observation with its date, series, value line and line span."""
    start = lines.index("observations:")
    blocks, cur, last = [], None, None
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        if not line.startswith(" ") and not line.startswith("- "):
            break  # the next top-level key ends the observations
        if line.startswith("- "):
            if cur is not None:
                cur["end"] = last + 1
                blocks.append(cur)
            match = BLOCK_HEAD.match(line)
            if not match:
                raise common.SourceError(f"unexpected observation line in the frontier file: {line}")
            cur = {"date": match.group(1), "start": i, "series": None, "value": None}
        else:
            if cur is None:
                raise common.SourceError("indented line before the first observation")
            if line.startswith("  series: "):
                cur["series"] = line[len("  series: "):].strip()
            elif line.startswith("  value: "):
                cur["value"] = i
        last = i
    if cur is not None:
        cur["end"] = last + 1
        blocks.append(cur)
    for b in blocks:
        if b["series"] is None or b["value"] is None:
            raise common.SourceError(f"observation at line {b['start'] + 1} has no series or value")
    return blocks


def block_lines(series, date, value):
    out = [f"- date: '{date}'", f"  series: {series}", f"  value: {value}", f"  source: {SOURCE}"]
    if series == TOTAL:
        out.append(f"  note: {TOTAL_NOTE}")
    return out


def fetch():
    counts = parse_counts(common.get(TAP_URL))
    today = common.today()

    text = (common.ROOT / FRONTIER).read_text(encoding="utf-8")
    lines = text.split("\n")
    blocks = locate_observations(lines)
    stored = {}
    for b in blocks:
        key = (b["series"], b["date"])
        if key in stored:
            raise common.SourceError(f"duplicate observation {key} in the frontier file")
        stored[key] = b

    stored_years = {int(b["date"]) for b in blocks if b["series"] == PER_YEAR}
    missing = sorted(stored_years - set(counts))
    if missing:
        raise common.SourceError(f"discovery years in the frontier file are missing from the TAP result: {missing}")

    years = sorted(counts)
    running, cumulative = 0, {}
    for year in years:
        running += counts[year]
        cumulative[year] = running
    total = running

    totals = [b for b in blocks if b["series"] == TOTAL]
    latest = max(totals, key=lambda b: b["date"])
    previous_total = int(lines[latest["value"]].split(":", 1)[1])
    if total < previous_total * SHARP_DROP:
        raise common.SourceError(f"the total fell from {previous_total} to {total}, more than expected")

    desired = []
    for year in years:
        desired.append((PER_YEAR, str(year), counts[year]))
        desired.append((CUMULATIVE, str(year), cumulative[year]))
    if (TOTAL, today) in stored or total != previous_total:
        desired.append((TOTAL, today, total))

    messages, edits, inserts = [], [], []
    for series, date, value in desired:
        b = stored.get((series, date))
        if b is None:
            inserts.append((series, date, value))
            if series == PER_YEAR:
                messages.append(f"{date} discoveries: new year, {value:,} planets")
            elif series == CUMULATIVE:
                messages.append(f"Cumulative planets to {date}: new year, {value:,}")
            else:
                messages.append(f"Confirmed planets: {previous_total:,} -> {value:,} (dated {date})")
            continue
        old = int(lines[b["value"]].split(":", 1)[1])
        if old != value:
            edits.append((b["value"], value))
            if series == PER_YEAR:
                messages.append(f"{date} discoveries: {old:,} -> {value:,}")
            elif series == CUMULATIVE:
                messages.append(f"Cumulative planets to {date}: {old:,} -> {value:,}")
            else:
                messages.append(f"Confirmed planets: {old:,} -> {value:,} (dated {date}, updated in place)")

    if not edits and not inserts:
        return []

    for index, value in edits:
        lines[index] = f"  value: {value}"
    for series, date, value in inserts:
        same = [b for b in locate_observations(lines) if b["series"] == series]
        earlier = [b for b in same if b["date"] < date]
        position = earlier[-1]["end"] if earlier else same[0]["start"]
        lines[position:position] = block_lines(series, date, value)

    common.write_if_changed(FRONTIER, "\n".join(lines))

    after = {(b["series"], b["date"]): int(lines[b["value"]].split(":", 1)[1])
             for b in locate_observations(lines)}
    for series, date, value in desired:
        if after.get((series, date)) != value:
            raise RuntimeError(f"frontier file does not hold {series} {date} = {value} after the update")
    return messages
