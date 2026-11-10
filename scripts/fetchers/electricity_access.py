"""Refresh the extreme-poverty frontier from Our World in Data's copy of the World Bank Poverty and Inequality Platform.

The World rows of share-of-the-population-with-access-to-electricity.csv give, per year, the share of the world population living
on less than the international access threshold in the source's column. Values are rounded to two decimal places. The
source extrapolates the most recent World values from national accounts, so the newest years can be revised when the
source publishes a new release. Only observations whose source is this fetcher's source are changed. A year the source
publishes and the frontier does not yet have is added. A year the source no longer publishes is an error.
"""
import csv
import io
import re

from . import common

FRONTIER = "data/frontiers/development/electricity-access.yaml"
URL = "https://ourworldindata.org/grapher/share-of-the-population-with-access-to-electricity.csv?country=OWID_WRL"
COLUMN = "Access to electricity (% of population)"
SOURCE_ID = "owid-electricity-access"
ID_COLUMNS = ("Entity", "Code", "Year")
MIN_YEARS = 20
FIRST_YEAR = 1990  # rows before this are not used


def read_world(raw):
    """Return {year: value} for the World rows. Raises SourceError if the format looks wrong."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    header = reader.fieldnames or []
    print("DIAG header: " + " | ".join(header))
    missing = [c for c in ID_COLUMNS + (COLUMN,) if c not in header]
    if missing:
        raise common.SourceError(f"columns {missing} are missing from the OWID CSV; header was {header}")

    world = {}
    for row in reader:
        if row["Entity"] != "World" or row["Code"] != "OWID_WRL":
            continue
        year = row["Year"].strip()
        if not re.fullmatch(r"-?\d+", year):
            raise common.SourceError(f"World row has a bad year: {year!r}")
        if int(year) < FIRST_YEAR:
            continue  # the source's placeholder and early rows; the frontier starts at FIRST_YEAR
        text = row[COLUMN].strip()
        if text == "":
            continue
        try:
            value = float(text)
        except ValueError as exc:
            raise common.SourceError(f"World {year} is not a number: {text!r}") from exc
        if year in world:
            raise common.SourceError(f"World {year} appears more than once")
        world[int(year)] = round(value, 2)

    if len(world) < MIN_YEARS:
        raise common.SourceError(f"only {len(world)} World years found; expected at least {MIN_YEARS}")
    return world


def render(values):
    return "\n".join(f"- {{date: '{y}', value: {values[y]:.2f}, source: {SOURCE_ID}}}" for y in sorted(values))


def fetch():
    raw = common.get(URL)
    world = read_world(raw)
    years = sorted(world)
    print(f"DIAG World years: {len(years)}, {years[0]} to {years[-1]}")
    for y in years:
        print(f"DIAG source World {y}: {world[y]:.2f}")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {str(o["date"]): round(float(o["value"]), 2) for o in observations}
    removed = sorted(set(old) - {str(y) for y in world})
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing observations, e.g. {removed[:3]}")

    changes = []
    for y in years:
        key = str(y)
        if key not in old:
            changes.append(f"{y}: extreme poverty {world[y]:.2f}% added")
        elif old[key] != world[y]:
            print(f"DIAG mismatch {y}: frontier {old[key]:.2f}, source {world[y]:.2f}")
            changes.append(f"{y}: extreme poverty {old[key]:.2f}% -> {world[y]:.2f}%")
    if not changes:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if sep and any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    if not sep:
        head, sep = text.rstrip("\n"), "\nobservations:\n"
    path.write_text(head + sep + render(world) + "\n", encoding="utf-8")
    return changes
