"""Refresh the Erdős problems frontier from the teorth/erdosproblems database (Apache-2.0)."""
import csv
import io

import yaml

from . import common

FRONTIER = "data/frontiers/mathematics/erdos-problems.yaml"
DATASET = "data/datasets/erdos-problems"
BASE = "https://raw.githubusercontent.com/teorth/erdosproblems/main/data/"
COLUMNS = ["number", "prize", "status", "status_last_update", "informal_status",
           "informal_last_update", "formal_status", "formal_last_update",
           "statement_formalized", "tags", "comments"]


def _state(entry, key):
    value = entry.get(key) or {}
    return value if isinstance(value, dict) else {"state": value}


def _cell(value):
    if value is None:
        return ""
    return str(value)


def build_csv(problems):
    rows = []
    for p in problems:
        status = _state(p, "status")
        informal = _state(p, "informal_status")
        formal = _state(p, "formal_status")
        formalized = _state(p, "formalized")
        rows.append({
            "number": _cell(p.get("number")),
            "prize": _cell(p.get("prize")),
            "status": _cell(status.get("state")),
            "status_last_update": _cell(status.get("last_update")),
            "informal_status": _cell(informal.get("state")),
            "informal_last_update": _cell(informal.get("last_update")),
            "formal_status": _cell(formal.get("state")),
            "formal_last_update": _cell(formal.get("last_update")),
            "statement_formalized": _cell(formalized.get("state")),
            "tags": ";".join(p.get("tags") or []),
            "comments": _cell(p.get("comments")),
        })
    rows.sort(key=lambda r: int(r["number"]) if r["number"].isdigit() else 10**9)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def fetch():
    raw_yaml = common.get(BASE + "problems.yaml")
    raw_history = common.get(BASE + "statistics_history.csv")
    problems = yaml.safe_load(raw_yaml)
    if not isinstance(problems, list) or len(problems) < 1000:
        raise common.SourceError("problems.yaml did not contain the expected list of problems")

    before = {i["id"]: (i["status"], i.get("status_detail")) for i in common.load(FRONTIER).get("items", [])}
    csv_text = build_csv(problems)
    csv_changed = common.write_if_changed(f"{DATASET}/problems.csv", csv_text)
    common.write_if_changed(f"{DATASET}/statistics_history.csv", raw_history)
    if not csv_changed:
        return []

    common.set_readme_row(f"{DATASET}/README.md", "Retrieved", common.today())
    common.set_readme_row(f"{DATASET}/README.md", "Original problems.yaml SHA-256", common.sha256(raw_yaml))
    common.set_readme_row(f"{DATASET}/README.md", "problems.csv SHA-256", common.sha256(csv_text.encode()))
    common.set_readme_row(f"{DATASET}/README.md", "statistics_history.csv SHA-256", common.sha256(raw_history))
    common.run_script("scripts/import_erdos_problems.py")

    after = {i["id"]: (i["status"], i.get("status_detail")) for i in common.load(FRONTIER).get("items", [])}
    changes = []
    for pid in sorted(set(after) - set(before), key=lambda x: int(x) if x.isdigit() else 10**9):
        changes.append(f"Problem {pid} added ({after[pid][1]})")
    for pid in sorted(set(before) & set(after), key=lambda x: int(x) if x.isdigit() else 10**9):
        if before[pid] != after[pid]:
            changes.append(f"Problem {pid}: {before[pid][1]} -> {after[pid][1]}")
    return changes or ["Database entries updated (no status changes)"]
