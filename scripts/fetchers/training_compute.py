"""Refresh the training-compute frontier from Epoch AI's notable AI models file (CC BY 4.0).

Source: https://epoch.ai/data/notable_ai_models.csv, linked from https://epoch.ai/data/ai-models.
A model is a record when its estimated training compute is larger than that of every notable model
published before it (models on the same date are taken largest first). The records block is rebuilt
from the file each time, so the frontier always matches Epoch's latest estimates. Only facts derived
from the file are stored (model, date, compute, developer, Epoch's confidence); the file itself is
not copied.

The run prints DIAG lines (row counts, the latest records, and every value that differs from the
frontier file) so a dry run shows whether the stored records match Epoch's data.
"""
import csv
import io
import re

import yaml

from . import common

FRONTIER = "data/frontiers/ai/training-compute.yaml"
URL = "https://epoch.ai/data/notable_ai_models.csv"
SOURCE = "epoch-notable-models"
SERIES = "notable-models"
# Epoch revises compute estimates and adds older models; a changed estimate can add or remove
# records, which refresh.py still sends to review.
REVISES_PAST = True
NEEDED = ["Model", "Organization", "Publication date", "Training compute (FLOP)", "Confidence"]
MIN_ROWS = 500       # the file had several thousand rows in November 2026
MIN_WITH_COMPUTE = 300
CONFIRMED = {"Confident"}   # Epoch's own confidence rating for the compute estimate


def _rows(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    missing = [c for c in NEEDED if c not in fields]
    if missing:
        raise common.SourceError(f"{URL}: missing columns {missing}; header is {fields}")
    rows = list(reader)
    if len(rows) < MIN_ROWS:
        raise common.SourceError(f"{URL}: only {len(rows)} rows (expected at least {MIN_ROWS})")
    usable = []
    for r in rows:
        date, flop = r["Publication date"].strip(), r["Training compute (FLOP)"].strip()
        if not flop or not date:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise common.SourceError(f"{URL}: unexpected date {date!r} for {r['Model']!r}")
        try:
            value = float(flop)
        except ValueError:
            raise common.SourceError(f"{URL}: compute for {r['Model']!r} is not a number: {flop!r}") from None
        if value <= 0:
            raise common.SourceError(f"{URL}: compute for {r['Model']!r} is not positive: {flop!r}")
        usable.append((date, value, r))
    if len(usable) < MIN_WITH_COMPUTE:
        raise common.SourceError(f"{URL}: only {len(usable)} models with a compute estimate")
    print(f"DIAG {len(rows)} rows, {len(usable)} with a date and a training compute estimate")
    return usable


def build(usable):
    usable = sorted(usable, key=lambda t: (t[0], -t[1], t[2]["Model"]))
    records, best = [], None
    for date, value, r in usable:
        if best is not None and value <= best:
            continue
        best = value
        confidence = r["Confidence"].strip() or "not given"
        org = ", ".join(" ".join(o.split()) for o in r["Organization"].split(",") if o.strip())
        parts = [f"developer {org}" if org else "",
                 f"Epoch confidence in the estimate: {confidence}"]
        records.append({
            "date": date,
            "value": value,
            "series": SERIES,
            "holder": " ".join(r["Model"].split()),
            "conditions": "; ".join(p for p in parts if p),
            "status": "confirmed" if confidence in CONFIRMED else "claimed",
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
    for r in records[-5:]:
        print(f"DIAG latest record {r['date']} {r['value']:g} {r['holder']} ({r['status']})")
    old = common.load(FRONTIER).get("records") or []
    key = lambda r: (str(r["date"]), r["holder"])  # noqa: E731
    old_by, new_by = {key(r): r for r in old}, {key(r): r for r in records}
    changes = []
    for k in sorted(set(old_by) - set(new_by)):
        changes.append(f"no longer a record: {k[1]} ({k[0]})")
        print(f"DIAG removed {k[0]} {k[1]}")
    for k in sorted(set(new_by) - set(old_by)):
        r = new_by[k]
        changes.append(f"new record: {r['holder']} {r['value']:g} FLOP ({r['date']})")
        print(f"DIAG added {r['date']} | {r['value']!r} | {r['holder']} | {r['conditions']} | {r['status']}")
    for k in sorted(set(old_by) & set(new_by)):
        a, b = old_by[k], new_by[k]
        if float(a["value"]) != b["value"] or {**a, "value": 0, "date": ""} != {**b, "value": 0, "date": ""}:
            changes.append(f"changed: {b['holder']} ({b['date']})")
            print(f"DIAG mismatch {k[0]} {k[1]}: file {a}, source {b}")
    print(f"DIAG {len(records)} records from source, {len(old)} in file")
    if not changes:
        return []
    _replace_records(common.ROOT / FRONTIER, records)
    return changes
