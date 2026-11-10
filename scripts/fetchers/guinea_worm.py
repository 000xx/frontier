"""Refresh the guinea worm frontier's human case counts from Our World in Data's CSV export.

The World row of OWID's grapher "Reported cases of guinea worm disease" (WHO data, processed by
Our World in Data) gives the reported human cases per year. Counts are copied as whole numbers.
Only observations from this source are rewritten. A year that OWID no longer publishes is an
error, because existing observations are never deleted automatically.
"""
import csv
import io
import re

import yaml

from . import common

FRONTIER = "data/frontiers/health/guinea-worm.yaml"
URL = "https://ourworldindata.org/grapher/number-of-reported-guinea-worm-dracunculiasis-cases.csv?country=OWID_WRL"
SOURCE_ID = "owid-guinea-worm"
ID_COLUMNS = ("Entity", "Code", "Year")
MIN_YEARS = 20


def read_counts(raw):
    """Return {year: count} for the World rows. Raises SourceError if the format looks wrong."""
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    header = reader.fieldnames or []
    missing = [c for c in ID_COLUMNS if c not in header]
    if missing:
        raise common.SourceError(f"columns missing from the OWID CSV: {', '.join(missing)}")
    value_columns = [c for c in header if c not in ID_COLUMNS]
    if len(value_columns) != 1:
        raise common.SourceError(f"expected one value column, found {value_columns}")
    column = value_columns[0]

    counts = {}
    for row in reader:
        if row["Entity"] != "World" or row["Code"] != "OWID_WRL":
            continue
        year = row["Year"].strip()
        if not re.fullmatch(r"\d{4}", year):
            raise common.SourceError(f"World row has a bad year: {year!r}")
        text = (row[column] or "").strip()
        if text == "":
            continue
        try:
            number = float(text)
        except ValueError as exc:
            raise common.SourceError(f"World {year}: {text!r} is not a number") from exc
        if number < 0 or number != int(number):
            raise common.SourceError(f"World {year}: {text!r} is not a whole count")
        if year in counts:
            raise common.SourceError(f"World {year} appears more than once")
        counts[year] = int(number)
    if len(counts) < MIN_YEARS:
        raise common.SourceError(f"only {len(counts)} World years found (expected at least {MIN_YEARS})")
    return counts


def render_observations(entries):
    return yaml.safe_dump({"observations": entries}, sort_keys=False, allow_unicode=True, width=110)


def replace_block(text, entries):
    match = re.search(r"(?ms)^observations:.*?(?=^[A-Za-z_])", text)
    if not match:
        raise RuntimeError(f"could not find the observations block in {FRONTIER}")
    return text[:match.start()] + render_observations(entries) + text[match.end():]


def fetch():
    counts = read_counts(common.get(URL))
    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    old = common.load(FRONTIER).get("observations") or []

    owid = {str(o["date"]): o for o in old if o.get("source") == SOURCE_ID}
    gone = sorted(set(owid) - set(counts))
    if gone:
        raise common.SourceError(f"OWID no longer publishes {', '.join(gone)}")

    messages = []
    for year in sorted(counts):
        if year not in owid:
            messages.append(f"{year} added: {counts[year]} (OWID)")
        elif owid[year]["value"] != counts[year]:
            messages.append(f"{year}: {owid[year]['value']} -> {counts[year]} (OWID)")

    others = [o for o in old if o.get("source") != SOURCE_ID]
    ours = [{"date": year, "value": counts[year], "source": SOURCE_ID} for year in sorted(counts)]
    new = others + ours
    if new == old:
        return []

    path.write_text(replace_block(text, new), encoding="utf-8")
    if common.load(FRONTIER).get("observations") != new:
        raise common.SourceError("observations did not round-trip after the edit")
    return messages
