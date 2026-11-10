"""Refresh the GPQA Diamond frontier from Epoch AI's benchmark data (CC BY 4.0).

Source: https://epoch.ai/data/benchmark_data.zip, linked from https://epoch.ai/benchmarks/use-this-data,
member gpqa_diamond.csv (Epoch's own runs). A model is a record when its mean score beats every
model with an earlier release date (models released the same day are taken best first); a score of
zero is never a record. The records block is rebuilt from the file each time; only facts derived from
it are stored, and the zip is not copied. DIAG lines show counts, the latest records and every
difference from the frontier file.
"""
import csv
import io
import re
import zipfile

import yaml

from . import common

FRONTIER = "data/frontiers/ai/gpqa-diamond.yaml"
URL = "https://epoch.ai/data/benchmark_data.zip"
SOURCE = "epoch-benchmarks"
FILES = {
    "epoch-runs": "gpqa_diamond.csv",
}
MODEL, SCORE, DATE, ORG, STDERR = "Model version", "mean_score", "Release date", "Organization", "stderr"
MIN_ROWS = 50          # placeholder until the first run shows the row count
REVISES_PAST = True    # Epoch re-runs models and fixes release dates; removals still go to review


def _read(zf, series, name):
    if name not in zf.namelist():
        raise common.SourceError(f"{URL}: {name} is missing; members are {zf.namelist()}")
    reader = csv.DictReader(io.StringIO(zf.read(name).decode("utf-8-sig")))
    fields = reader.fieldnames or []
    missing = [c for c in (MODEL, SCORE, DATE, ORG, STDERR) if c not in fields]
    if missing:
        raise common.SourceError(f"{name}: missing columns {missing}; header is {fields}")
    rows = list(reader)
    if len(rows) < MIN_ROWS:
        raise common.SourceError(f"{name}: only {len(rows)} rows (expected at least {MIN_ROWS})")
    usable = []
    for r in rows:
        date, score = r[DATE].strip(), r[SCORE].strip()
        if not date or not score:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise common.SourceError(f"{name}: unexpected release date {date!r} for {r[MODEL]!r}")
        try:
            value = float(score)
        except ValueError:
            raise common.SourceError(f"{name}: score for {r[MODEL]!r} is not a number: {score!r}") from None
        if not 0 <= value <= 1:
            raise common.SourceError(f"{name}: score for {r[MODEL]!r} is outside 0 to 1: {score!r}")
        usable.append((date, value, r))
    print(f"DIAG {series} ({name}): {len(rows)} rows, {len(usable)} with a release date and a score, "
          f"{len({u[2][MODEL] for u in usable})} distinct models")
    return usable


def _record(series, date, value, r):
    parts = []
    org = ", ".join(" ".join(o.split()) for o in r[ORG].split(",") if o.strip())
    if org:
        parts.append(f"developer {org}")
    stderr = r[STDERR].strip()
    if stderr:
        try:
            parts.append(f"standard error {round(float(stderr) * 100, 2)} points")
        except ValueError:
            raise common.SourceError(f"stderr for {r[MODEL]!r} is not a number: {stderr!r}") from None
    parts.append("Epoch AI evaluation; date is the model's release date")
    return {
        "date": date,
        "value": round(value * 100, 2),
        "series": series,
        "holder": " ".join(r[MODEL].split()),
        "conditions": "; ".join(parts),
        "status": "confirmed",
        "source": SOURCE,
    }


def build(zf):
    records = []
    for series, name in FILES.items():
        best = None
        for date, value, r in sorted(_read(zf, series, name), key=lambda t: (t[0], -t[1], t[2][MODEL])):
            if value <= 0 or (best is not None and value <= best):
                continue
            best = value
            records.append(_record(series, date, value, r))
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
    try:
        zf = zipfile.ZipFile(io.BytesIO(common.get(URL)))
    except zipfile.BadZipFile as exc:
        raise common.SourceError(f"{URL} is not a zip file: {exc}") from None
    records = build(zf)
    for series in FILES:
        for r in [r for r in records if r["series"] == series][-3:]:
            print(f"DIAG latest {series}: {r['date']} {r['value']} {r['holder']}")
    old = common.load(FRONTIER).get("records") or []
    key = lambda r: (r["series"], str(r["date"]), r["holder"])  # noqa: E731
    old_by, new_by = {key(r): r for r in old}, {key(r): r for r in records}
    changes = []
    for k in sorted(set(old_by) - set(new_by)):
        changes.append(f"no longer a record: {k[0]} {k[2]} ({k[1]})")
        print(f"DIAG removed {k}")
    for k in sorted(set(new_by) - set(old_by)):
        r = new_by[k]
        changes.append(f"new record: {r['series']} {r['holder']} {r['value']}% ({r['date']})")
        print(f"DIAG added {r['series']} | {r['date']} | {r['value']!r} | {r['holder']} | {r['conditions']}")
    for k in sorted(set(old_by) & set(new_by)):
        if old_by[k] != new_by[k]:
            changes.append(f"changed: {k[0]} {k[2]} ({k[1]})")
            print(f"DIAG mismatch {k}: file {old_by[k]}, source {new_by[k]}")
    print(f"DIAG {len(records)} records from source, {len(old)} in file")
    if not changes:
        return []
    _replace_records(common.ROOT / FRONTIER, records)
    return changes
