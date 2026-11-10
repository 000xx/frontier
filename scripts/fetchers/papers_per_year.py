"""Refresh the papers-per-year frontier from OpenAlex's works API (CC0 data).

One request groups all works in the index by publication year, for years from FIRST_YEAR to the last full year. The
count for each year is stored as an observation. New years are added. The last three full years are rewritten when
they change; older years are kept as they are, and any change to them is printed in the run log only, because OpenAlex
keeps adding and correcting records for older years.
"""
import datetime as dt
import json

from . import common

FRONTIER = "data/frontiers/knowledge/papers-per-year.yaml"
URL = ("https://api.openalex.org/works?filter=publication_year:{first}-{last}"
       "&group_by=publication_year")
SOURCE_ID = "openalex-works"
SERIES_ID = "works"
FIRST_YEAR = 1960
REWRITE_WINDOW = 3
MIN_YEARS = 30


def yearly_counts(last_full):
    url = URL.format(first=FIRST_YEAR, last=last_full)
    data = json.loads(common.get(url).decode("utf-8"))
    groups = data.get("group_by")
    if not isinstance(groups, list):
        raise common.SourceError("no group_by list in the OpenAlex response")
    counts = {}
    for group in groups:
        key = str(group.get("key"))
        if not key.isdigit():
            raise common.SourceError(f"unexpected publication year key {key!r}")
        year = int(key)
        if FIRST_YEAR <= year <= last_full:
            counts[year] = int(group.get("count", 0))
    if len(counts) < MIN_YEARS:
        raise common.SourceError(f"only {len(counts)} years found; expected at least {MIN_YEARS}")
    return counts


def fetch():
    last_full = dt.date.today().year - 1
    world = yearly_counts(last_full)
    years = sorted(world)
    print(f"DIAG years: {len(years)}, {years[0]} to {years[-1]}")
    for year in years:
        print(f"DIAG value {year} {world[year]}")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {int(o["date"]): int(o["value"]) for o in observations}

    recent_from = last_full - REWRITE_WINDOW + 1
    keep = {}
    changes = []
    for year in sorted(set(old) | set(world)):
        if year not in world:
            keep[year] = old[year]
            print(f"DIAG {year}: missing from source; kept")
        elif year not in old:
            keep[year] = world[year]
            changes.append(f"{year}: {world[year]} works added")
        elif old[year] == world[year]:
            keep[year] = old[year]
        elif year >= recent_from:
            keep[year] = world[year]
            changes.append(f"{year}: {old[year]} -> {world[year]} works")
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
