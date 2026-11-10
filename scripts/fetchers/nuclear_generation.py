"""Refresh the nuclear generation frontier from Our World in Data's copy of Ember and Energy Institute data.

The World rows of nuclear-energy-generation.csv give nuclear electricity generation in terawatt-hours for each year. The file has exactly one value column; the values are written as the source gives them.
"""
import csv
import io
import re

from . import common

FRONTIER = "data/frontiers/energy/nuclear-generation.yaml"
URL = "https://ourworldindata.org/grapher/nuclear-energy-generation.csv?country=OWID_WRL"
SOURCE_ID = "owid-nuclear-energy-generation"
SERIES = "nuclear"
ID_COLUMNS = ["Entity", "Code", "Year"]
MIN_WORLD_YEARS = 10


def read_world(raw):
    """Return {year: terawatt-hours} for the World rows. Raises SourceError if the format looks wrong."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    missing = [c for c in ID_COLUMNS if c not in fields]
    value_columns = [c for c in fields if c not in ID_COLUMNS]
    if missing or len(value_columns) != 1:
        raise common.SourceError(f"unexpected columns in the OWID CSV: {fields}")
    column = value_columns[0]
    print(f"DIAG value column: {column!r}")

    world = {}
    for row in reader:
        if row["Entity"] != "World":
            continue
        year = row["Year"].strip()
        if not re.fullmatch(r"\d{4}", year):
            raise common.SourceError(f"World row has a bad year: {year!r}")
        text = row[column].strip()
        if text == "":
            continue  # year not yet published
        if int(year) in world:
            raise common.SourceError(f"World {year} appears more than once")
        try:
            world[int(year)] = float(text)
        except ValueError as exc:
            raise common.SourceError(f"World {year} is not a number: {text!r}") from exc

    if len(world) < MIN_WORLD_YEARS:
        raise common.SourceError(f"only {len(world)} World years found; expected at least {MIN_WORLD_YEARS}")
    return world


def render_observations(world):
    return [f"- {{date: '{year}', series: {SERIES}, value: {world[year]!r}, source: {SOURCE_ID}}}"
            for year in sorted(world)]


def fetch():
    world = read_world(common.get(URL))
    years = sorted(world)
    print(f"DIAG World rows: {len(years)} years, {years[0]} to {years[-1]}")
    print("DIAG newest: " + "; ".join(f"{y} {world[y]!r} TWh" for y in years[-3:]))

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {str(o["date"]): float(o["value"]) for o in observations}
    new = {str(y): v for y, v in world.items()}

    removed = sorted(set(old) - set(new))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing observations, e.g. {removed[:3]}")

    changes = [f"{y}: nuclear {new[y]!r} TWh added" for y in sorted(set(new) - set(old))]
    changes += [f"{y}: nuclear {old[y]!r} -> {new[y]!r} TWh" for y in sorted(set(old) & set(new))
                if old[y] != new[y]]
    print(f"DIAG existing: {len(old)} observations; changed: {len(changes) - len(set(new) - set(old))}")
    for line in changes[:60]:
        print(f"DIAG change: {line}")
    if not changes:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:")
    if not sep or any(line.strip() and line.strip() != "[]" and not line.startswith("- {")
                      for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    path.write_text(head + sep + "\n" + "\n".join(render_observations(world)) + "\n", encoding="utf-8")
    return changes

