"""Refresh the undernourishment frontier from Our World in Data's copy of FAO's SDG 2.1.1 series.

Reads the World rows (OWID_WRL) of the grapher prevalence-of-undernourishment CSV and rewrites the observations
block when a year is added or a value changes. Years that disappear from the source stop the run.
"""
import csv
import io
import re

from . import common

FRONTIER = "data/frontiers/food/undernourishment.yaml"
URL = "https://ourworldindata.org/grapher/prevalence-of-undernourishment.csv?country=OWID_WRL"
SOURCE_ID = "owid-undernourishment"
SERIES_ID = "world"
COLUMN = "2.1.1 prevalence of undernourishment - Value (percent)"
MIN_YEARS = 20


def read_world(raw):
    """Return {year: value} for the World rows. Raises SourceError if the format looks wrong."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if (reader.fieldnames or []) != ["Entity", "Code", "Year", COLUMN]:
        raise common.SourceError(f"unexpected CSV header: {reader.fieldnames}")
    world = {}
    for row in reader:
        if row["Entity"] != "World" or row["Code"] != "OWID_WRL":
            continue
        year = row["Year"].strip()
        if not re.fullmatch(r"\d{4}", year):
            raise common.SourceError(f"World row has a bad year: {year!r}")
        year = int(year)
        text = row[COLUMN].strip()
        if text == "":
            continue
        try:
            value = float(text)
        except ValueError as exc:
            raise common.SourceError(f"World {year} is not a number: {text!r}") from exc
        if year in world:
            raise common.SourceError(f"World {year} appears more than once")
        world[year] = round(value, 2)
    if len(world) < MIN_YEARS:
        raise common.SourceError(f"only {len(world)} World years found; expected at least {MIN_YEARS}")
    return world


def fetch():
    world = read_world(common.get(URL))
    years = sorted(world)
    print(f"DIAG World rows: {len(years)} years, {years[0]} to {years[-1]}")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {int(o["date"]): round(float(o["value"]), 2) for o in observations}

    removed = sorted(set(old) - set(world))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing years, e.g. {removed[:3]}")

    changes = []
    for year in sorted(world):
        if year not in old:
            changes.append(f"{year}: undernourishment {world[year]} % added")
        elif old[year] != world[year]:
            changes.append(f"{year}: undernourishment {old[year]} -> {world[year]} %")
            print(f"DIAG mismatch: {year} file {old[year]} source {world[year]}")
    print(f"DIAG existing: {len(old)} observations; changes: {len(changes)}")
    if not changes:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    lines = [f"- {{date: '{y}', series: {SERIES_ID}, value: {world[y]!r}, source: {SOURCE_ID}}}" for y in years]
    path.write_text(head + sep + "\n".join(lines) + "\n", encoding="utf-8")
    return changes
