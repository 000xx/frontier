"""Refresh the open-access frontier from OpenAlex's works API (CC0 data).

For each publication year, counts article works grouped by open_access.is_oa and stores the share of open-access
articles to one decimal. New years are added. The last three full years are rewritten when they change. Older
years are never rewritten: OpenAlex can still add open-access copies to them, and any such change is only printed
in the run log, so the frontier keeps the values it was built from.
"""
import datetime as dt
import json

from . import common

FRONTIER = "data/frontiers/knowledge/open-access.yaml"
URL = ("https://api.openalex.org/works?filter=publication_year:{year},type:article"
       "&group_by=open_access.is_oa")
SOURCE_ID = "openalex"
SERIES_ID = "articles"
FIRST_YEAR = 2000
REWRITE_WINDOW = 3  # the last three full years are kept current
MIN_YEARS = 20


def year_share(year):
    """Return the open-access share (percent, one decimal) for one year, or None if the year has no articles."""
    data = json.loads(common.get(URL.format(year=year)).decode("utf-8"))
    groups = data.get("group_by")
    if not isinstance(groups, list):
        raise common.SourceError(f"{year}: no group_by list in the OpenAlex response")
    counts = {}
    for group in groups:
        key = str(group.get("key"))
        if key not in ("true", "false"):
            raise common.SourceError(f"{year}: unexpected open-access key {key!r}")
        counts[key] = int(group.get("count", 0))
    total = counts.get("true", 0) + counts.get("false", 0)
    if total == 0:
        return None
    return round(100 * counts.get("true", 0) / total, 1)


def fetch():
    last_full = dt.date.today().year - 1
    world = {}
    for year in range(FIRST_YEAR, last_full + 1):
        share = year_share(year)
        if share is not None:
            world[year] = share
    if len(world) < MIN_YEARS:
        raise common.SourceError(f"only {len(world)} years found; expected at least {MIN_YEARS}")
    years = sorted(world)
    print(f"DIAG years: {len(years)}, {years[0]} to {years[-1]}")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {int(o["date"]): round(float(o["value"]), 1) for o in observations}

    recent_from = last_full - REWRITE_WINDOW + 1
    keep = {}
    changes = []
    for year in sorted(set(old) | set(world)):
        if year not in world:
            keep[year] = old[year]
            print(f"DIAG {year}: missing from source; kept")
        elif year not in old:
            keep[year] = world[year]
            changes.append(f"{year}: open-access share {world[year]} % added")
        elif old[year] == world[year]:
            keep[year] = old[year]
        elif year >= recent_from:
            keep[year] = world[year]
            changes.append(f"{year}: open-access share {old[year]} -> {world[year]} %")
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
    lines = [f"- {{date: '{y}', series: {SERIES_ID}, value: {keep[y]!r}, source: {SOURCE_ID}}}" for y in sorted(keep)]
    path.write_text(head + sep + "\n".join(lines) + "\n", encoding="utf-8")
    return changes
