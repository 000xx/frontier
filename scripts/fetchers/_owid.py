"""Shared helper for fetchers whose frontier observations come from Our World in Data grapher CSVs.

Not a fetcher itself (refresh.py skips modules whose names start with "_"). A fetcher using it
looks like this:

    from . import common, _owid
    FRONTIER = "data/frontiers/<domain>/<id>.yaml"
    SPECS = [
        _owid.Spec(series="world", source="owid-<slug>",
                   url="https://ourworldindata.org/grapher/<slug>.csv?country=OWID_WRL",
                   entity="World", column="<exact column header>", decimals=2, first_year=1990),
    ]
    def fetch():
        return _owid.refresh(FRONTIER, SPECS)

What it does, per spec: downloads the CSV, takes the rows for `entity`, reads `column` for each
year (or day), and makes the frontier's observations for that series match the source exactly.
New dates are added; changed values are updated and reported; a date the source no longer has
raises SourceError. Observations of other series are kept as they are. The observations block
is rewritten in one-line flow style and only when something changed. A first run on a frontier
with no observations for a series fills that series, so the same code builds and refreshes it.
"""
import csv
import io
import re
from dataclasses import dataclass

import yaml

from . import common

DATE_COLUMNS = ("Year", "Day")


@dataclass
class Spec:
    series: str
    source: str
    url: str
    column: str
    entity: str = "World"
    decimals: int | None = None   # round values; None keeps the source's full precision
    first_year: int | None = None
    scale: float = 1.0            # multiply source values, e.g. 1e-9 to report billions
    min_rows: int = 5             # fewer rows than this means the source broke


def _read(spec):
    raw = common.get(spec.url)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    date_col = next((c for c in DATE_COLUMNS if c in fields), None)
    if "Entity" not in fields or date_col is None or spec.column not in fields:
        raise common.SourceError(f"{spec.url}: expected Entity, Year or Day and {spec.column!r}; "
                                 f"got {fields}")
    values = {}
    for row in reader:
        if row["Entity"] != spec.entity:
            continue
        date, cell = row[date_col].strip(), row[spec.column].strip()
        if not re.fullmatch(r"\d{4}(-\d{2}-\d{2})?", date):
            raise common.SourceError(f"{spec.url}: bad date {date!r}")
        if spec.first_year and int(date[:4]) < spec.first_year:
            continue
        if cell == "":
            continue
        try:
            value = float(cell) * spec.scale
        except ValueError:
            raise common.SourceError(f"{spec.url}: {spec.entity} {date}: not a number: {cell!r}") from None
        if spec.decimals is not None:
            value = round(value, spec.decimals)
        if date in values:
            raise common.SourceError(f"{spec.url}: {spec.entity} {date} appears twice")
        values[date] = int(value) if spec.decimals == 0 else value
    if len(values) < spec.min_rows:
        raise common.SourceError(f"{spec.url}: only {len(values)} rows for {spec.entity!r}")
    return values


def _render(obs):
    text = yaml.safe_dump(obs, default_flow_style=True, sort_keys=False, allow_unicode=True,
                          width=10_000).strip()
    return "- " + text


def _replace_block(path, observations):
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^observations:[ \t]*(\[\])?[ \t]*\n((?:[ -].*\n|\n)*)", text)
    lines = "".join(_render(o) + "\n" for o in observations)
    if match:
        text = text[:match.start()] + "observations:\n" + lines + text[match.end():]
    else:
        text = text.rstrip("\n") + "\nobservations:\n" + lines
    path.write_text(text, encoding="utf-8")


def refresh(frontier, specs):
    data = common.load(frontier)
    existing = data.get("observations") or []
    managed = {s.series for s in specs}
    kept = [o for o in existing if o.get("series") not in managed]
    old = {(o["series"], str(o["date"])): o for o in existing if o.get("series") in managed}

    new = {}
    for spec in specs:
        values = _read(spec)
        print(f"DIAG {spec.series}: {len(values)} rows, latest "
              + ", ".join(f"{d}={values[d]}" for d in sorted(values)[-3:]))
        for date, value in values.items():
            new[(spec.series, date)] = (value, spec.source)

    removed = sorted(set(old) - set(new))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing observations, "
                                 f"e.g. {removed[:3]}")
    changes = []
    for key in sorted(new, key=lambda k: (k[1], k[0])):
        value, _ = new[key]
        if key not in old:
            changes.append(f"{key[0]} {key[1]}: {value} added")
        elif float(old[key]["value"]) != float(value):
            changes.append(f"{key[0]} {key[1]}: {old[key]['value']} -> {value}")
            print(f"DIAG mismatch {key[0]} {key[1]}: file {old[key]['value']}, source {value}")
    if not changes:
        return []

    rebuilt = list(kept)
    for (series, date), (value, source) in sorted(new.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        obs = {"date": date, "series": series, "value": value, "source": source}
        prior = old.get((series, date), {})
        for extra in ("low", "high", "note"):
            if extra in prior:
                obs[extra] = prior[extra]
        rebuilt.append(obs)
    _replace_block(common.ROOT / frontier, rebuilt)
    if len(changes) > 40:
        changes = changes[:40] + [f"... and {len(changes) - 40} more"]
    return changes
