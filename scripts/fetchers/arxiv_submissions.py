"""Refresh the arXiv submissions frontier from arXiv's monthly submissions CSV.

Sums the monthly counts by calendar year. Only years with twelve months are used, and the series starts in 1992,
the first full year. New complete years are added; a change to an existing year is written and reported.
"""
import csv
import io
from collections import defaultdict

from . import common

FRONTIER = "data/frontiers/knowledge/arxiv-submissions.yaml"
URL = "https://arxiv.org/stats/get_monthly_submissions"
SOURCE_ID = "arxiv-monthly-csv"
SERIES_ID = "all"
FIRST_YEAR = 1992
MIN_YEARS = 30


def yearly_totals(raw):
    """Return {year: total} for complete calendar years. Raises SourceError if the format looks wrong."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if (reader.fieldnames or []) != ["month", "submissions"]:
        raise common.SourceError(f"unexpected CSV header: {reader.fieldnames}")
    sums = defaultdict(int)
    months = defaultdict(int)
    for row in reader:
        month = row["month"].strip()
        text = row["submissions"].strip()
        if len(month) != 10 or not text.isdigit():
            raise common.SourceError(f"bad row: {row!r}")
        year = int(month[:4])
        sums[year] += int(text)
        months[year] += 1
    totals = {y: sums[y] for y in sums if y >= FIRST_YEAR and months[y] == 12}
    if len(totals) < MIN_YEARS:
        raise common.SourceError(f"only {len(totals)} complete years found; expected at least {MIN_YEARS}")
    return totals


def fetch():
    totals = yearly_totals(common.get(URL))
    years = sorted(totals)
    print(f"DIAG complete years: {len(years)}, {years[0]} to {years[-1]}")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {int(o["date"]): int(o["value"]) for o in observations}

    removed = sorted(set(old) - set(totals))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing years, e.g. {removed[:3]}")

    changes = []
    for year in years:
        if year not in old:
            changes.append(f"{year}: {totals[year]} new submissions added")
        elif old[year] != totals[year]:
            changes.append(f"{year}: {old[year]} -> {totals[year]} new submissions")
            print(f"DIAG mismatch: {year} file {old[year]} source {totals[year]}")
    print(f"DIAG existing: {len(old)} observations; changes: {len(changes)}")
    if not changes:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    lines = [f"- {{date: '{y}', series: {SERIES_ID}, value: {totals[y]}, source: {SOURCE_ID}}}" for y in years]
    path.write_text(head + sep + "\n".join(lines) + "\n", encoding="utf-8")
    return changes
