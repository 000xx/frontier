"""Refresh the Antarctic ozone hole frontier from NASA Ozone Watch's annual table.

The page has an HTML table with one row per year: year, date of the maximum, maximum area (million km2), date of
the minimum ozone, and minimum ozone (DU). Years with no data (NASA lists 1995 that way) are skipped, not guessed.
Existing years must keep their values; revised values are written and reported; years that disappear are an error.
"""
import html
import re

from . import common

FRONTIER = "data/frontiers/earth/ozone-hole.yaml"
URL = "https://ozonewatch.gsfc.nasa.gov/statistics/annual_data.html"
SOURCE_ID = "nasa-ozone-watch"
SERIES = "max-area"
FIRST_YEAR = 1979
MIN_YEARS = 40


def _cells(row_html):
    cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.S | re.I)
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip() for c in cells]


def read_table(raw):
    """Return {year: max_area_million_km2}. Raises SourceError if the table does not look right."""
    text = raw.decode("utf-8", errors="replace")
    years = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S | re.I):
        cells = _cells(row)
        if len(cells) < 3 or not re.fullmatch(r"\d{4}", cells[0]):
            continue
        year = int(cells[0])
        if year in years:
            raise common.SourceError(f"year {year} appears more than once")
        if not re.fullmatch(r"\d+(\.\d+)?", cells[2]):
            continue  # no data for this year
        area = float(cells[2])
        if not 0 < area < 40:
            raise common.SourceError(f"area for {year} is outside a plausible range: {area}")
        years[year] = round(area, 1)

    if not years:
        raise common.SourceError("no year rows found in the NASA ozone table")
    if min(years) != FIRST_YEAR:
        raise common.SourceError(f"first year is {min(years)}, expected {FIRST_YEAR}")
    if len(years) < MIN_YEARS:
        raise common.SourceError(f"only {len(years)} years found; expected at least {MIN_YEARS}")
    return years


def render_observations(years):
    return [f"- {{date: '{year}', series: {SERIES}, value: {years[year]:.1f}, source: {SOURCE_ID}}}"
            for year in sorted(years)]


def fetch():
    raw = common.get(URL)
    years = read_table(raw)
    ordered = sorted(years)
    print(f"DIAG NASA years: {len(ordered)}, {ordered[0]} to {ordered[-1]}; "
          f"latest: {ordered[-1]} {years[ordered[-1]]:.1f} million km2")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {int(o["date"]): round(float(o["value"]), 1) for o in observations}

    removed = sorted(set(old) - set(years))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing years, e.g. {removed[:3]}")
    changed = [y for y in sorted(old) if old[y] != years[y]]
    for y in changed:
        print(f"DIAG mismatch: {y} frontier {old[y]:.1f} source {years[y]:.1f}")
    added = [y for y in ordered if y not in old]
    for y in added:
        print(f"DIAG added: {y} {years[y]:.1f}")
    if not added and not changed:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    path.write_text(head + sep + "\n".join(render_observations(years)) + "\n", encoding="utf-8")
    return ([f"{y}: maximum area {years[y]:.1f} million km2 added" for y in added]
            + [f"{y}: maximum area {old[y]:.1f} -> {years[y]:.1f} million km2" for y in changed])
