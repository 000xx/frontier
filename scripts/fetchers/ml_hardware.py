"""Refresh the ML hardware frontier from Epoch AI's machine learning hardware data (CC BY 4.0).

Source: https://epoch.ai/data/ml_hardware.csv, linked from https://epoch.ai/data/machine-learning-hardware.
Each row is one AI accelerator with its release date and its performance in FLOP/s by number format. Epoch
compiles these figures from hardware datasheets. The frontier uses the column "Tensor-FP16/BF16 performance
(FLOP/s)", converted to TFLOP/s. A record is an accelerator whose figure beats every accelerator released
earlier (chips released on the same day are taken best first); a missing or zero figure is never a record.
The records block is rebuilt from the file each time; only facts derived from it are stored, and the CSV is
not copied. DIAG lines show counts, the latest records and every difference from the frontier file.
"""
import csv
import io
import re

import yaml

from . import common

FRONTIER = "data/frontiers/computing/ml-hardware.yaml"
URL = "https://epoch.ai/data/ml_hardware.csv"
SOURCE = "epoch-ml-hardware"
SERIES = "tensor-fp16-bf16"
NAME, MAKER, DATE, PERF = "Hardware name", "Manufacturer", "Release date", "Tensor-FP16/BF16 performance (FLOP/s)"
MIN_ROWS = 150         # the file had about 180 accelerators in November 2026
REVISES_PAST = True    # Epoch corrects datasheet figures and release dates; removals still go to review


def _read():
    raw = common.get(URL)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    missing = [c for c in (NAME, MAKER, DATE, PERF) if c not in fields]
    if missing:
        raise common.SourceError(f"{URL}: missing columns {missing}; header is {fields[:12]}...")
    rows = list(reader)
    if len(rows) < MIN_ROWS:
        raise common.SourceError(f"{URL}: only {len(rows)} rows (expected at least {MIN_ROWS})")
    usable = []
    for r in rows:
        date, perf = r[DATE].strip(), r[PERF].strip()
        if not date or not perf:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise common.SourceError(f"{URL}: unexpected release date {date!r} for {r[NAME]!r}")
        try:
            value = float(perf)
        except ValueError:
            raise common.SourceError(f"{URL}: performance for {r[NAME]!r} is not a number: {perf!r}") from None
        if value <= 0:
            continue
        usable.append((date, value / 1e12, r))
    print(f"DIAG {len(rows)} rows, {len(usable)} with a release date and tensor FP16/BF16 performance")
    return usable


def _record(date, value, r):
    maker = " ".join(r[MAKER].split())
    parts = []
    if maker:
        parts.append(f"manufacturer {maker}")
    parts.append("figure from the hardware datasheet as compiled by Epoch AI; date is the release date")
    return {
        "date": date,
        "value": round(value, 2),
        "series": SERIES,
        "holder": " ".join(r[NAME].split()),
        "conditions": "; ".join(parts),
        "status": "claimed",
        "source": SOURCE,
    }


def build():
    records = []
    best = None
    for date, value, r in sorted(_read(), key=lambda t: (t[0], -t[1], t[2][NAME])):
        if best is not None and round(value, 2) <= best:
            continue
        best = round(value, 2)
        records.append(_record(date, value, r))
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
    records = build()
    for r in records[-3:]:
        print(f"DIAG latest {SERIES}: {r['date']} {r['value']} {r['holder']}")
    old = common.load(FRONTIER).get("records") or []
    key = lambda r: (r["series"], str(r["date"]), r["holder"])  # noqa: E731
    old_by, new_by = {key(r): r for r in old}, {key(r): r for r in records}
    changes = []
    for k in sorted(set(old_by) - set(new_by)):
        changes.append(f"no longer a record: {k[2]} ({k[1]})")
        print(f"DIAG removed {k}")
    for k in sorted(set(new_by) - set(old_by)):
        r = new_by[k]
        changes.append(f"new record: {r['holder']} {r['value']} TFLOP/s ({r['date']})")
        print(f"DIAG added {r['series']} | {r['date']} | {r['value']!r} | {r['holder']} | {r['conditions']}")
    for k in sorted(set(old_by) & set(new_by)):
        if old_by[k] != new_by[k]:
            changes.append(f"changed: {k[2]} ({k[1]})")
            print(f"DIAG mismatch {k}: file {old_by[k]}, source {new_by[k]}")
    print(f"DIAG {len(records)} records from source, {len(old)} in file")
    if not changes:
        return []
    _replace_records(common.ROOT / FRONTIER, records)
    return changes
