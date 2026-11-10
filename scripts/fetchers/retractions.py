"""Refresh the retractions frontier from the Retraction Watch CSV that Crossref publishes on GitLab.

Counts rows whose RetractionNature is "Retraction" by the year of RetractionDate, for complete years from 2000.
New complete years are added. The last three full years are rewritten when they change. Older years are not
rewritten, because the database gains earlier records over time; a change to one is printed in the run log only.
"""
import csv
import datetime as dt
import io
import re
from collections import Counter

from . import common

FRONTIER = "data/frontiers/knowledge/retractions.yaml"
URL = "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"
SOURCE_ID = "retraction-watch-csv"
SERIES_ID = "all"
FIRST_YEAR = 2000
REWRITE_WINDOW = 3
MIN_YEARS = 20
REQUIRED = ["RetractionNature", "RetractionDate"]


def yearly_counts(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise common.SourceError(f"columns missing from the Retraction Watch CSV: {', '.join(missing)}")
    counts = Counter()
    rows = 0
    for row in reader:
        rows += 1
        if row["RetractionNature"] != "Retraction":
            continue
        m = re.search(r"\b(\d{4})\b", row["RetractionDate"])
        if m:
            counts[int(m.group(1))] += 1
    if rows < 50000:
        raise common.SourceError(f"only {rows} rows; the file looks cut short")
    years = {y: counts[y] for y in counts if y >= FIRST_YEAR}
    last_full = dt.date.today().year - 1
    years = {y: v for y, v in years.items() if y <= last_full}
    if len(years) < MIN_YEARS:
        raise common.SourceError(f"only {len(years)} years found; expected at least {MIN_YEARS}")
    return years


def fetch():
    world = yearly_counts(common.get(URL))
    years = sorted(world)
    print(f"DIAG years: {len(years)}, {years[0]} to {years[-1]}")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {int(o["date"]): int(o["value"]) for o in observations}

    last_full = dt.date.today().year - 1
    recent_from = last_full - REWRITE_WINDOW + 1
    keep = {}
    changes = []
    for year in sorted(set(old) | set(world)):
        if year not in world:
            keep[year] = old[year]
            print(f"DIAG {year}: missing from source; kept")
        elif year not in old:
            keep[year] = world[year]
            changes.append(f"{year}: {world[year]} retraction notices added")
        elif old[year] == world[year]:
            keep[year] = old[year]
        elif year >= recent_from:
            keep[year] = world[year]
            changes.append(f"{year}: {old[year]} -> {world[year]} retraction notices")
        else:
            keep[year] = old[year]
            print(f"DIAG older year revised at source, not rewritten: {year} file {old[year]} source {world[year]}")
    print(f"DIAG existing: {len(old)} observations; changes: {len(changes)}")
    if not changes:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    lines = [f"- {{date: '{y}', series: {SERIES_ID}, value: {keep[y]}, source: {SOURCE_ID}}}" for y in sorted(keep)]
    path.write_text(head + sep + "\n".join(lines) + "\n", encoding="utf-8")
    return changes
