"""Refresh the malaria frontier's WHO estimates from the WHO Global Health Observatory.

Reads the global rows of the GHO indicators MALARIA_EST_CASES and MALARIA_EST_DEATHS
(the World malaria report estimates, with WHO's low and high bounds), rebuilds
data/datasets/who-malaria-estimates/estimates.csv and copies the values into the
frontier's `observations`. WHO's data terms (see the dataset's NOTICE.md) allow no
alteration, so values are copied exactly: unrounded, with only trailing ".0" dropped.

WHO revises every past year with each World malaria report, so a new report changes
most existing observations and the refresh marks the run for review. The change lines
say which years were revised. Certified countries (items), candidates and events are
not touched.
"""
import csv
import io
import json
import re
from decimal import Decimal, InvalidOperation

import yaml

from . import common

FRONTIER = "data/frontiers/health/malaria.yaml"
DATASET = "data/datasets/who-malaria-estimates"
SOURCE_ID = "who-gho-malaria-estimates"
API = "https://ghoapi.azureedge.net/api/{code}?$filter=SpatialDim%20eq%20%27GLOBAL%27"
INDICATORS = {"cases": "MALARIA_EST_CASES", "deaths": "MALARIA_EST_DEATHS"}
CSV_ORDER = ["cases", "deaths"]      # order of rows in estimates.csv
COLUMNS = ["year", "measure", "value", "low", "high"]
MIN_YEARS = 20                       # 2000 onward; far fewer means the source broke


def _number(raw, what):
    """WHO's number as an exact string with trailing zero decimals dropped, and as an int."""
    if raw is None:
        raise common.SourceError(f"{what} is missing")
    try:
        d = Decimal(str(raw))
    except InvalidOperation as exc:
        raise common.SourceError(f"{what} is not a number: {raw!r}") from exc
    if not d.is_finite() or d < 0 or d != d.to_integral_value():
        raise common.SourceError(f"{what} is not a whole, non-negative number: {raw!r}")
    n = int(d)
    return str(n), n


def read_indicator(measure):
    code = INDICATORS[measure]
    raw = common.get(API.format(code=code))
    try:
        payload = json.loads(raw, parse_float=Decimal, parse_int=Decimal)
    except ValueError as exc:
        raise common.SourceError(f"{code}: response is not JSON") from exc
    records = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise common.SourceError(f"{code}: response has no 'value' list")

    rows, dates = {}, set()
    for r in records:
        if r.get("IndicatorCode") != code or r.get("SpatialDim") != "GLOBAL":
            raise common.SourceError(f"{code}: unexpected record {r.get('Id')} "
                                     f"({r.get('IndicatorCode')}, {r.get('SpatialDim')})")
        if r.get("TimeDimType") != "YEAR":
            raise common.SourceError(f"{code}: record {r.get('Id')} has TimeDimType {r.get('TimeDimType')!r}")
        for dim in ("Dim1", "Dim2", "Dim3"):
            if r.get(dim) is not None:
                raise common.SourceError(f"{code}: record {r.get('Id')} has a {dim} breakdown "
                                         f"({r.get(dim)!r}); the format has changed")
        year = str(r.get("TimeDim"))
        if not re.fullmatch(r"\d{4}", year):
            raise common.SourceError(f"{code}: record {r.get('Id')} has year {r.get('TimeDim')!r}")
        if year in rows:
            raise common.SourceError(f"{code}: more than one global record for {year}")
        value = _number(r.get("NumericValue"), f"{code} {year} NumericValue")
        low = _number(r.get("Low"), f"{code} {year} Low")
        high = _number(r.get("High"), f"{code} {year} High")
        if not low[1] <= value[1] <= high[1]:
            raise common.SourceError(f"{code} {year}: value {value[0]} is outside its range {low[0]}-{high[0]}")
        rows[year] = {"value": value, "low": low, "high": high}
        dates.add(str(r.get("Date") or ""))
    if len(rows) < MIN_YEARS:
        raise common.SourceError(f"{code}: only {len(rows)} global records (expected at least {MIN_YEARS})")
    return rows, dates


def build_csv(data):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for measure in CSV_ORDER:
        for year in sorted(data[measure]):
            row = data[measure][year]
            writer.writerow([year, measure, row["value"][0], row["low"][0], row["high"][0]])
    return out.getvalue()


def read_csv(path):
    target = common.ROOT / path
    if not target.exists():
        return {}
    with open(target, encoding="utf-8", newline="") as f:
        return {(r["measure"], r["year"]): (r["value"], r["low"], r["high"]) for r in csv.DictReader(f)}


def _set_row(path, label, value):
    """Like common.set_readme_row, but leaves the line break after the row alone
    (common's pattern ends in \\s*$, which also swallows a following blank line)."""
    target = common.ROOT / path
    text = target.read_text(encoding="utf-8")
    pattern = re.compile(r"(?m)^\|[ \t]*" + re.escape(label) + r"[ \t]*\|[^\n]*\|[ \t]*$")
    if not pattern.search(text):
        raise RuntimeError(f"no '{label}' row in {path}")
    target.write_text(pattern.sub(lambda m: f"| {label} | {value} |", text, count=1), encoding="utf-8")


def _fmt(n):
    return f"{n:,}"


def _scalar(key, value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=True, width=110).rstrip("\n")
    if isinstance(value, int):
        return f"{key}: {value}"
    return yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=True, width=110).rstrip("\n")


def render_observations(entries):
    lines = ["observations:"]
    for e in entries:
        for i, (key, value) in enumerate(e.items()):
            text = _scalar(key, value)
            for j, line in enumerate(text.split("\n")):
                prefix = "- " if i == 0 and j == 0 else "  "
                lines.append(prefix + line)
    return "\n".join(lines) + "\n"


def replace_block(text, new_block):
    match = re.search(r"(?ms)^observations:\n.*?(?=^[A-Za-z_])", text)
    if not match:
        raise RuntimeError(f"could not find the observations block in {FRONTIER}")
    return text[:match.start()] + new_block + text[match.end():]


def update_observations(data):
    """Return the new observations list (existing entries keep their order and any extra keys)."""
    frontier = common.load(FRONTIER)
    old = frontier.get("observations") or []
    seen, entries, series_order = set(), [], []
    for e in old:
        series, year = e.get("series"), str(e.get("date"))
        if e.get("source") != SOURCE_ID or series not in data:
            entries.append(dict(e))
            continue
        if year not in data[series]:
            raise common.SourceError(f"WHO no longer gives a {series} estimate for {year}; "
                                     "existing observations are never deleted automatically")
        row = data[series][year]
        new = dict(e)
        new["value"], new["low"], new["high"] = row["value"][1], row["low"][1], row["high"][1]
        entries.append(new)
        seen.add((series, year))
        if series not in series_order:
            series_order.append(series)
    for series in series_order + [s for s in CSV_ORDER if s not in series_order]:
        missing = sorted(y for y in data[series] if (series, y) not in seen)
        if not missing:
            continue
        # insert after the last existing entry of this series, keeping years ascending
        last = max((i for i, e in enumerate(entries)
                    if e.get("series") == series and e.get("source") == SOURCE_ID), default=len(entries) - 1)
        for k, year in enumerate(missing):
            row = data[series][year]
            entries.insert(last + 1 + k, {"date": year, "series": series, "value": row["value"][1],
                                          "low": row["low"][1], "high": row["high"][1], "source": SOURCE_ID})
    return old, entries


def fetch():
    data, dates = {}, set()
    for measure in CSV_ORDER:
        data[measure], d = read_indicator(measure)
        dates |= d

    before_csv = read_csv(f"{DATASET}/estimates.csv")
    for (measure, year) in before_csv:
        if year not in data.get(measure, {}):
            raise common.SourceError(f"WHO no longer gives a {measure} estimate for {year}")

    csv_text = build_csv(data)
    old_obs, new_obs = update_observations(data)
    obs_changed = old_obs != new_obs
    print("DIAG malaria:", {m: (len(data[m]), max(data[m]), data[m][max(data[m])]["value"][0]) for m in data},
          "dates", sorted(dates), "obs_changed", obs_changed)  # DIAG
    csv_changed = common.write_if_changed(f"{DATASET}/estimates.csv", csv_text)
    if not csv_changed and not obs_changed:
        return []

    readme = f"{DATASET}/README.md"
    _set_row(readme, "Retrieved", common.today())
    _set_row(readme, "estimates.csv SHA-256", common.sha256(csv_text.encode()))
    gho_dates = sorted(d[:10] for d in dates if d)
    if gho_dates:
        _set_row(readme, "GHO records last updated",
                              f"{gho_dates[-1]} (the `Date` field on every record)" if len(gho_dates) == 1
                              else f"{gho_dates[0]} to {gho_dates[-1]} (the `Date` field on the records)")

    if obs_changed:
        path = common.ROOT / FRONTIER
        text = path.read_text(encoding="utf-8")
        path.write_text(replace_block(text, render_observations(new_obs)), encoding="utf-8")

    changes, revised, added = [], {}, {}
    for measure in CSV_ORDER:
        for year in sorted(data[measure]):
            row = data[measure][year]
            new = (row["value"][0], row["low"][0], row["high"][0])
            old = before_csv.get((measure, year))
            if old is None:
                added.setdefault(measure, []).append(year)
                changes.append(f"{year} {measure} added: {_fmt(row['value'][1])} "
                               f"(range {_fmt(row['low'][1])}-{_fmt(row['high'][1])})")
            elif old != new:
                revised.setdefault(measure, []).append(year)
                o = [int(x) for x in old]
                changes.append(f"{year} {measure} revised by WHO: {_fmt(o[0])} -> {_fmt(row['value'][1])} "
                               f"(range {_fmt(o[1])}-{_fmt(o[2])} -> "
                               f"{_fmt(row['low'][1])}-{_fmt(row['high'][1])})")
    summary = []
    for measure in CSV_ORDER:
        if revised.get(measure):
            ys = revised[measure]
            summary.append(f"WHO revised {len(ys)} earlier {measure} year(s): {', '.join(ys)}")
        if added.get(measure):
            summary.append(f"New {measure} year(s): {', '.join(added[measure])}")
    if revised or added:
        summary.append("A new World malaria report is likely out: check the report named in the dataset README, "
                       "NOTICE.md credit line, update.notes and the 2024 figures quoted in metric.explainer")
    if not changes:
        changes = ["estimates.csv rewritten to match the source (no value changes)"]
    return summary + changes
