"""Refresh the GPU clusters frontier from Epoch AI's GPU Clusters data (CC BY 4.0).

Source: https://epoch.ai/data/gpu_clusters.csv, linked from https://epoch.ai/data/gpu-clusters.
Each row is one AI compute cluster that Epoch has tracked, with its status, its size in H100 equivalents,
its first operational date and Epoch's certainty. The frontier uses rows that Epoch marks as existing and
included in its standard analysis, and whose first operational date is known. A record is a cluster whose
H100-equivalent count beats every cluster that became operational on an earlier date (clusters on the same
day are taken largest first). Epoch's own estimates are used as published; the CSV is not copied.
DIAG lines show counts, the latest records and every difference from the frontier file.
"""
import csv
import io
import re

import yaml

from . import common

FRONTIER = "data/frontiers/ai/gpu-clusters.yaml"
URL = "https://epoch.ai/data/gpu_clusters.csv"
SOURCE = "epoch-gpu-clusters"
SERIES = "h100-equivalents"
NAME, STATUS, STANDARD, H100, DATE = ("Name", "Status", "Include in Standard Analysis", "H100 equivalents",
                                     "First Operational Date")
OWNER, CHIP, CERTAINTY = "Owner", "Chip type (primary)", "Certainty"
MIN_ROWS = 300         # the file had 482 rows in November 2026


def _read():
    raw = common.get(URL)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    missing = [c for c in (NAME, STATUS, STANDARD, H100, DATE, OWNER, CHIP, CERTAINTY) if c not in fields]
    if missing:
        raise common.SourceError(f"{URL}: missing columns {missing}; header starts {fields[:8]}")
    rows = list(reader)
    if len(rows) < MIN_ROWS:
        raise common.SourceError(f"{URL}: only {len(rows)} rows (expected at least {MIN_ROWS})")
    usable = []
    for r in rows:
        if r[STATUS].strip() != "Existing" or r[STANDARD].strip() != "True":
            continue
        date, size = r[DATE].strip(), r[H100].strip()
        if not date or not size:
            continue
        if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", date):
            raise common.SourceError(f"{URL}: unexpected date {date!r} for {r[NAME]!r}")
        try:
            value = float(size)
        except ValueError:
            raise common.SourceError(f"{URL}: H100 equivalents for {r[NAME]!r} is not a number: {size!r}") from None
        if value <= 0:
            continue
        usable.append((date, value, r))
    print(f"DIAG {len(rows)} rows, {len(usable)} existing standard-analysis clusters with a date and H100 count")
    return usable


def _record(date, value, r):
    parts = []
    owner = " ".join(r[OWNER].split())
    if owner:
        parts.append(f"owner {owner}")
    chip = " ".join(r[CHIP].split())
    if chip:
        parts.append(f"primary chip {chip}")
    certainty = " ".join(r[CERTAINTY].split())
    if certainty:
        parts.append(f"Epoch certainty {certainty.lower()}")
    parts.append("H100-equivalents estimated by Epoch AI; date is the first operational date")
    return {
        "date": date,
        "value": round(value),
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
        if best is not None and round(value) <= best:
            continue
        best = round(value)
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
        changes.append(f"new record: {r['holder']} {r['value']} H100-equivalents ({r['date']})")
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
