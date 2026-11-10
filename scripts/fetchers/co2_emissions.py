"""Refresh the world CO2 emissions frontier from Our World in Data's copy of the Global Carbon Budget.

The grapher CSV has one row per entity and year. The World rows (code OWID_WRL) hold "Annual CO₂ emissions" in tonnes
(fossil fuels and cement, excluding land-use change). Values are written in billion tonnes (Gt), rounded to three
decimals (one million tonnes). Years with no value are skipped. Existing years must keep their values; new years are added.
"""
import csv
import io
import re

from . import common

FRONTIER = "data/frontiers/earth/co2-emissions.yaml"
URL = "https://ourworldindata.org/grapher/annual-co2-emissions-per-country.csv?v=1&csvType=full&useColumnShortNames=false"
SOURCE_ID = "owid-annual-co2-emissions"
SERIES = "world-fossil-co2"
COLUMN = "Annual CO₂ emissions"
REQUIRED = ["Entity", "Code", "Year", COLUMN]
FIRST_YEAR = 1900
MIN_YEARS = 100


def read_world(raw):
    """Return {year: Gt CO2}. Raises SourceError if the format looks wrong."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise common.SourceError(f"columns missing from the OWID CSV: {', '.join(missing)}; "
                                 f"found {', '.join(reader.fieldnames or [])[:300]}")
    world = {}
    for row in reader:
        if row["Entity"] != "World" or row["Code"] != "OWID_WRL":
            continue
        year = row["Year"].strip()
        if not re.fullmatch(r"\d{4}", year):
            raise common.SourceError(f"World row has a bad year: {year!r}")
        year = int(year)
        if year < FIRST_YEAR:
            continue
        if year in world:
            raise common.SourceError(f"World {year} appears more than once")
        cell = row[COLUMN].strip()
        if cell == "":
            continue
        if not re.fullmatch(r"\d+(\.\d+)?(e\+?\d+)?", cell):
            raise common.SourceError(f"World {year} emissions are not a number: {cell!r}")
        world[year] = round(float(cell) / 1e9, 3)
    if len(world) < MIN_YEARS:
        raise common.SourceError(f"only {len(world)} World years found; expected at least {MIN_YEARS}")
    last = max(world)
    gaps = [y for y in range(min(world), last + 1) if y not in world]
    if gaps:
        raise common.SourceError(f"World years missing from the middle of the series: {gaps[:5]}")
    return world


def render_observations(values):
    return [f"- {{date: '{year}', series: {SERIES}, value: {values[year]:.3f}, source: {SOURCE_ID}}}"
            for year in sorted(values)]


def fetch():
    raw = common.get(URL)
    world = read_world(raw)
    ordered = sorted(world)
    print(f"DIAG OWID World years: {len(ordered)}, {ordered[0]} to {ordered[-1]}; "
          f"latest: {ordered[-1]} {world[ordered[-1]]:.3f} Gt")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {int(o["date"]): round(float(o["value"]), 3) for o in observations}

    removed = sorted(set(old) - set(world))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing years, e.g. {removed[:3]}")
    changed = [y for y in sorted(old) if old[y] != world[y]]
    for y in changed:
        print(f"DIAG mismatch: {y} frontier {old[y]:.3f} source {world[y]:.3f}")
    added = [y for y in ordered if y not in old]
    for y in added:
        print(f"DIAG added: {y} {world[y]:.3f}")
    if not added and not changed:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    path.write_text(head + sep + "\n".join(render_observations(world)) + "\n", encoding="utf-8")
    return ([f"{y}: {world[y]:.3f} Gt CO2 added" for y in added]
            + [f"{y}: {old[y]:.3f} -> {world[y]:.3f} Gt CO2" for y in changed])
