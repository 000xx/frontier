"""Refresh the global temperature frontier from NASA GISS's Global Land-Ocean Temperature Index.

The CSV has a title line and a header row beginning "Year" and containing "J-D" (the annual mean). Annual values are
in hundredths of a degree Celsius against the 1951 to 1980 baseline; "***" means the year is not yet complete.
NASA revises past years, so changed values are written and reported; refresh.py flags large changes for review.
Years that disappear from the source are an error, not a silent removal.
"""
import csv
import io
import re

from . import common

FRONTIER = "data/frontiers/earth/global-temperature.yaml"
URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
SOURCE_ID = "nasa-gistemp-annual"
SERIES = "gistemp-land-ocean"
FIRST_YEAR = 1880
MIN_YEARS = 100


def read_annual(raw):
    """Return {year: anomaly_celsius} from the J-D column. Raises SourceError if the format looks wrong."""
    lines = raw.decode("utf-8", errors="replace").splitlines()
    header_at = next((i for i, line in enumerate(lines) if line.split(",")[0].strip() == "Year"
                      and "J-D" in [c.strip() for c in line.split(",")]), None)
    if header_at is None:
        raise common.SourceError("no header row with Year and J-D columns in the NASA CSV")
    header = [c.strip() for c in lines[header_at].split(",")]
    jd = header.index("J-D")

    years = {}
    for row in csv.reader(io.StringIO("\n".join(lines[header_at + 1:]))):
        if not row or not re.fullmatch(r"\d{4}", row[0].strip()):
            continue
        year = int(row[0])
        if year in years:
            raise common.SourceError(f"year {year} appears more than once")
        cell = row[jd].strip() if jd < len(row) else ""
        if cell in ("", "***"):
            continue  # year not yet complete
        if not re.fullmatch(r"-?\d+", cell):
            raise common.SourceError(f"J-D for {year} is not a whole number of hundredths: {cell!r}")
        value = int(cell) / 100
        if not -2 < value < 3:
            raise common.SourceError(f"J-D for {year} is outside a plausible range: {value}")
        years[year] = round(value, 2)

    if min(years) != FIRST_YEAR:
        raise common.SourceError(f"first year is {min(years)}, expected {FIRST_YEAR}")
    if len(years) < MIN_YEARS:
        raise common.SourceError(f"only {len(years)} complete years found; expected at least {MIN_YEARS}")
    return years


def render_observations(years):
    return [f"- {{date: '{year}', series: {SERIES}, value: {years[year]:.2f}, source: {SOURCE_ID}}}"
            for year in sorted(years)]


def fetch():
    raw = common.get(URL)
    years = read_annual(raw)
    ordered = sorted(years)
    print(f"DIAG NASA years: {len(ordered)}, {ordered[0]} to {ordered[-1]}; "
          f"latest: {ordered[-1]} {years[ordered[-1]]:.2f} C")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {int(o["date"]): round(float(o["value"]), 2) for o in observations}

    removed = sorted(set(old) - set(years))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing years, e.g. {removed[:3]}")

    added = [y for y in ordered if y not in old]
    changed = [y for y in sorted(old) if y in years and old[y] != years[y]]
    for y in changed:
        print(f"DIAG mismatch: {y} frontier {old[y]:.2f} source {years[y]:.2f}")
    for y in added:
        print(f"DIAG added: {y} {years[y]:.2f}")
    if not added and not changed:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    path.write_text(head + sep + "\n".join(render_observations(years)) + "\n", encoding="utf-8")
    return ([f"{y}: anomaly {years[y]:.2f} C added" for y in added]
            + [f"{y}: anomaly {old[y]:.2f} -> {years[y]:.2f} C" for y in changed])
