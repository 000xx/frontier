"""Refresh the clean electricity share frontier from Our World in Data's copy of Ember's yearly electricity data.

The World rows of share-elec-by-source.csv give, per year, the share of electricity from each source. Low-carbon
is the sum of the six non-fossil columns (hydropower, solar, wind, nuclear, other renewables, bioenergy), rounded
to two decimals like the other values in the frontier file. Wind and solar are the source's own columns.
"""
import csv
import io
import math
import re

from . import common

FRONTIER = "data/frontiers/energy/clean-electricity-share.yaml"
URL = "https://ourworldindata.org/grapher/share-elec-by-source.csv?country=OWID_WRL"
SOURCE_ID = "owid-share-elec-by-source"
NON_FOSSIL = ["Hydropower", "Solar", "Wind", "Nuclear", "Other renewables", "Bioenergy"]
FOSSIL = ["Coal", "Gas", "Oil"]
REQUIRED = ["Entity", "Code", "Year"] + NON_FOSSIL + FOSSIL
SERIES = [("low-carbon", "Low-carbon"), ("wind", "Wind"), ("solar", "Solar")]
MIN_WORLD_YEARS = 20


def _number(text, year, column):
    try:
        return float(text)
    except ValueError as exc:
        raise common.SourceError(f"World {year}: {column} is not a number: {text!r}") from exc


def read_world(raw):
    """Return {year: {series: value}} for the World rows. Raises SourceError if the format looks wrong."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise common.SourceError(f"columns missing from the OWID CSV: {', '.join(missing)}")

    world = {}
    for row in reader:
        if row["Entity"] != "World" or row["Code"] != "OWID_WRL":
            continue
        year = row["Year"].strip()
        if not re.fullmatch(r"\d{4}", year):
            raise common.SourceError(f"World row has a bad year: {year!r}")
        year = int(year)
        if year in world:
            raise common.SourceError(f"World {year} appears more than once")
        cells = {c: row[c].strip() for c in NON_FOSSIL + FOSSIL}
        if all(v == "" for v in cells.values()):
            continue  # year not yet published
        blank = [c for c, v in cells.items() if v == ""]
        if blank:
            raise common.SourceError(f"World {year} has blank columns: {', '.join(blank)}")
        shares = {c: _number(cells[c], year, c) for c in NON_FOSSIL}
        world[year] = {
            "low-carbon": round(math.fsum(shares[c] for c in NON_FOSSIL), 2),
            "wind": round(shares["Wind"], 2),
            "solar": round(shares["Solar"], 2),
        }

    if len(world) < MIN_WORLD_YEARS:
        raise common.SourceError(f"only {len(world)} World years found; expected at least {MIN_WORLD_YEARS}")
    return world


def render_observations(table):
    lines = []
    for series, _ in SERIES:
        for year in sorted(table[series]):
            lines.append(f"- {{date: '{year}', series: {series}, value: {table[series][year]:.2f}, "
                         f"source: {SOURCE_ID}}}")
    return lines


def fetch():
    raw = common.get(URL)
    world = read_world(raw)
    years = sorted(world)
    print(f"DIAG World rows: {len(years)} years, {years[0]} to {years[-1]}")
    print(f"DIAG newest: " + "; ".join(f"{y} low {world[y]['low-carbon']:.2f} wind {world[y]['wind']:.2f} "
                                       f"solar {world[y]['solar']:.2f}" for y in years[-3:]))

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {(o["series"], str(o["date"])): round(float(o["value"]), 2) for o in observations}
    new = {}
    for series, _ in SERIES:
        for year, values in world.items():
            new[(series, str(year))] = values[series]

    removed = sorted(set(old) - set(new))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing observations, e.g. {removed[:3]}")

    labels = dict(SERIES)
    changes = []
    for key in sorted(set(new) - set(old), key=lambda k: (k[1], k[0])):
        changes.append(f"{key[1]}: {labels[key[0]]} {new[key]:.2f} added")
    for key in sorted(set(old) & set(new), key=lambda k: (k[1], k[0])):
        if old[key] != new[key]:
            changes.append(f"{key[1]}: {labels[key[0]]} {old[key]:.2f} -> {new[key]:.2f}")
    print(f"DIAG existing: {len(old)} observations; mismatches with source: {len(changes) - len(set(new) - set(old))}")
    for line in changes[:60]:
        print(f"DIAG change: {line}")

    if not changes:
        return []

    table = {series: {} for series, _ in SERIES}
    for (series, year), value in new.items():
        table[series][int(year)] = value
    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    rendered = head + sep + "\n".join(render_observations(table)) + "\n"
    path.write_text(rendered, encoding="utf-8")
    return changes
