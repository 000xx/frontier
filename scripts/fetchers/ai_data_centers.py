"""Refresh the ai-data-centers frontier from Epoch AI's Frontier Data Centers hub (CC BY 4.0).

Source: https://epoch.ai/data/data_centers/data_center_timelines.csv, linked from
https://epoch.ai/data/frontier-data-centers. Each row is one site's estimated status on one date.
A row is a record when its facility power is larger than every row dated before it, across all sites
(rows on the same date are taken largest first). Rows dated after the day of the run are Epoch's
projections and are left out; they enter the record line automatically once their date has passed.
The records block is rebuilt from the file each time; only facts derived from it are stored, and the
file is not copied, and Epoch's free-text construction notes are not stored. DIAG lines show counts,
the latest records and every difference from the frontier file.
"""
import csv
import datetime as dt
import io
import re

import yaml

from . import common

FRONTIER = "data/frontiers/ai/ai-data-centers.yaml"
URL = "https://epoch.ai/data/data_centers/data_center_timelines.csv"
SOURCE = "epoch-data-centers"
SERIES = "largest-site"
SITE, DATE, POWER, IT_POWER, STATUS = "Data center", "Date", "Power (MW)", "IT power (MW)", "Construction status"
MIN_ROWS = 400   # the file had 573 rows (76 sites) in November 2026
REVISES_PAST = True  # Epoch revises its site estimates; removed records still go to review


def _number(text, what):
    text = text.strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        raise common.SourceError(f"{URL}: {what} is not a number: {text!r}") from None


def _rows(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    missing = [c for c in (SITE, DATE, POWER, IT_POWER, STATUS) if c not in fields]
    if missing:
        raise common.SourceError(f"{URL}: missing columns {missing}; header is {fields}")
    rows = list(reader)
    if len(rows) < MIN_ROWS:
        raise common.SourceError(f"{URL}: only {len(rows)} rows (expected at least {MIN_ROWS})")
    today = dt.date.today().isoformat()
    usable, future = [], 0
    for r in rows:
        date = r[DATE].strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise common.SourceError(f"{URL}: unexpected date {date!r} for {r[SITE]!r}")
        power = _number(r[POWER], f"power for {r[SITE]!r} on {date}")
        if power is None or power <= 0:
            continue
        if date > today:
            future += 1
            continue
        usable.append((date, power, r))
    print(f"DIAG {len(rows)} rows; {len(usable)} dated up to {today} with a power value; "
          f"{future} later rows (projections) left out; {len({u[2][SITE] for u in usable})} sites")
    return usable


def build(usable):
    records, best = [], None
    for date, power, r in sorted(usable, key=lambda t: (t[0], -t[1], t[2][SITE])):
        if best is not None and power <= best:
            continue
        best = power
        parts = []
        it = _number(r[IT_POWER], f"IT power for {r[SITE]!r} on {date}")
        if it is not None:
            parts.append(f"IT power {it:g} MW")
        parts.append("Epoch AI estimate for this date")
        records.append({
            "date": date,
            "value": power,
            "series": SERIES,
            "holder": " ".join(r[SITE].split()),
            "conditions": "; ".join(parts),
            "status": "confirmed",
            "source": SOURCE,
        })
    return records


def _render(rec):
    return "- " + yaml.safe_dump(rec, default_flow_style=True, sort_keys=False, allow_unicode=True,
                                 width=10_000).strip()


def _replace_records(path, records):
    text = path.read_text(encoding="utf-8")
    block = "records:\n" + "".join(_render(r) + "\n" for r in records)
    match = re.search(r"(?m)^records:[ \t]*(\[\])?[ \t]*\n((?:[ -].*\n|\n)*)", text)
    if match:
        text = text[:match.start()] + block + text[match.end():]
    else:
        text = text.rstrip("\n") + "\n" + block
    path.write_text(text, encoding="utf-8")


def fetch():
    records = build(_rows(common.get(URL)))
    for r in records[-3:]:
        print(f"DIAG latest {r['date']} {r['value']:g} MW {r['holder']}")
    old = common.load(FRONTIER).get("records") or []
    key = lambda r: (str(r["date"]), r["holder"])  # noqa: E731
    old_by, new_by = {key(r): r for r in old}, {key(r): r for r in records}
    changes = []
    for k in sorted(set(old_by) - set(new_by)):
        changes.append(f"no longer a record: {k[1]} ({k[0]})")
        print(f"DIAG removed {k}")
    for k in sorted(set(new_by) - set(old_by)):
        r = new_by[k]
        changes.append(f"new record: {r['holder']} {r['value']:g} MW ({r['date']})")
        print(f"DIAG added {r['series']} | {r['date']} | {r['value']!r} | {r['holder']} | {r['conditions']}")
    for k in sorted(set(old_by) & set(new_by)):
        if old_by[k] != new_by[k]:
            changes.append(f"changed: {k[1]} ({k[0]})")
            print(f"DIAG mismatch {k}: file {old_by[k]}, source {new_by[k]}")
    print(f"DIAG {len(records)} records from source, {len(old)} in file")
    if not changes:
        return []
    _replace_records(common.ROOT / FRONTIER, records)
    return changes
