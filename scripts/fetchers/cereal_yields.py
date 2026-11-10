"""Refresh the cereal yields frontier from Our World in Data's copy of FAO's cereal yield data.

Reads the World rows (OWID_WRL) of the grapher cereal-yield CSV, keeps the values to four decimals as the
source gives them, and rewrites the observations block when a year is added or a value changes. Existing years
that disappear from the source stop the run: the frontier is never shortened by this fetcher.
"""
import csv
import io
import re

from . import common

FRONTIER = "data/frontiers/food/cereal-yields.yaml"
URL = "https://ourworldindata.org/grapher/cereal-yield.csv?country=OWID_WRL"
SOURCE_ID = "owid-cereal-yield"
SERIES_ID = "world"
COLUMN = "Cereals - Yield (tonnes per hectare)"
FIRST_YEAR = 1961
MIN_YEARS = 50  # the series runs 1961 onward; far fewer means the file was cut short


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
        world[year] = round(value, 4)
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
    old = {int(o["date"]): round(float(o["value"]), 4) for o in observations}

    removed = sorted(set(old) - set(world))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing years, e.g. {removed[:3]}")

    changes = []
    for year in sorted(world):
        if year not in old:
            changes.append(f"{year}: world cereal yield {world[year]:.4f} t/ha added")
        elif old[year] != world[year]:
            changes.append(f"{year}: world cereal yield {old[year]:.4f} -> {world[year]:.4f} t/ha")
            print(f"DIAG mismatch: {year} file {old[year]:.4f} source {world[year]:.4f}")
    print(f"DIAG existing: {len(old)} observations; changes: {len(changes)}")
    if not changes:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    lines = [f"- {{date: '{y}', series: {SERIES_ID}, value: {world[y]:.4f}, source: {SOURCE_ID}}}" for y in years]
    path.write_text(head + sep + "\n".join(lines) + "\n", encoding="utf-8")
    return changes
