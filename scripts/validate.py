#!/usr/bin/env python3
"""Validate every frontier file and report frontiers that are overdue for a check.

Usage:
  python scripts/validate.py            # errors fail the run; overdue frontiers are warnings
  python scripts/validate.py --strict   # overdue frontiers also fail the run
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CADENCE_DAYS = {"weekly": 7, "monthly": 31, "quarterly": 92, "yearly": 366}


class StringDateLoader(yaml.SafeLoader):
    """SafeLoader that leaves dates as strings, so 2026-11-09 and "2026-11" are treated alike."""


StringDateLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, Loader=StringDateLoader)


def parse_date(text):
    """Turn YYYY, YYYY-MM or YYYY-MM-DD into the earliest matching date."""
    parts = [int(p) for p in str(text).split("-")]
    while len(parts) < 3:
        parts.append(1)
    return dt.date(*parts)


def check_frontier(path, data, schema, domains, shapes, today):
    errors, warnings = [], []
    rel = path.relative_to(ROOT)

    for err in Draft202012Validator(schema).iter_errors(data):
        where = "/".join(str(p) for p in err.absolute_path) or "(top level)"
        errors.append(f"{rel}: {where}: {err.message}")
    if errors:
        return errors, warnings

    if data["id"] != path.stem:
        errors.append(f"{rel}: id '{data['id']}' does not match the file name '{path.stem}'")

    domain = domains.get(data["domain"])
    if domain is None:
        errors.append(f"{rel}: unknown domain '{data['domain']}'")
    else:
        if path.parent.name != data["domain"]:
            errors.append(f"{rel}: file should live in data/frontiers/{data['domain']}/")
        if data["subfield"] not in domain["subfields"]:
            errors.append(f"{rel}: subfield '{data['subfield']}' is not listed under domain '{data['domain']}'")

    for shape in [data["chart"]["primary"], *data["chart"].get("secondary", [])]:
        if shape not in shapes:
            errors.append(f"{rel}: unknown chart shape '{shape}'")

    source_ids = [s["id"] for s in data["sources"]]
    if len(source_ids) != len(set(source_ids)):
        errors.append(f"{rel}: duplicate source ids")
    series_ids = {s["id"] for s in data.get("series", [])}

    limit = data["metric"].get("limit")
    if limit and limit["source"] not in source_ids:
        errors.append(f"{rel}: metric limit cites unknown source '{limit['source']}'")

    for i, rec in enumerate(data["records"]):
        label = f"{rel}: records[{i}]"
        if rec["source"] not in source_ids:
            errors.append(f"{label}: unknown source '{rec['source']}'")
        if series_ids and rec.get("series") not in series_ids:
            errors.append(f"{label}: series '{rec.get('series')}' is not defined in this file")
        if parse_date(rec["date"]) > today:
            errors.append(f"{label}: date {rec['date']} is in the future")

    # A record must beat the previous best in its series, unless it is a retraction.
    best = {}
    higher = data["metric"]["direction"] == "higher"
    ordered = sorted(
        (r for r in data["records"] if r["status"] != "retracted"),
        key=lambda r: parse_date(r["date"]),
    )
    for rec in ordered:
        key = rec.get("series")
        prev = best.get(key)
        if prev is not None and ((rec["value"] <= prev) if higher else (rec["value"] >= prev)):
            warnings.append(
                f"{rel}: {rec['date']} value {rec['value']} in series '{key}' does not beat the earlier best {prev}"
            )
        else:
            best[key] = rec["value"]

    for i, ev in enumerate(data.get("events", [])):
        if parse_date(ev["date"]) > today:
            errors.append(f"{rel}: events[{i}]: date {ev['date']} is in the future")

    last = parse_date(data["update"]["last_checked"])
    due = last + dt.timedelta(days=CADENCE_DAYS[data["update"]["cadence"]])
    overdue = data["status"] != "paused" and due < today
    if overdue:
        warnings.append(f"{rel}: overdue for a check (last checked {last}, cadence {data['update']['cadence']})")

    return errors, warnings, overdue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="fail on overdue frontiers")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    args = parser.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    schema = json.loads((ROOT / "schema" / "frontier.schema.json").read_text(encoding="utf-8"))
    domains = {d["id"]: d for d in load_yaml(DATA / "domains.yaml")}
    shapes = {s["id"] for s in load_yaml(DATA / "chart-shapes.yaml")}

    all_errors, all_warnings, overdue_count, ids = [], [], 0, {}
    files = sorted((DATA / "frontiers").rglob("*.yaml"))
    for path in files:
        data = load_yaml(path)
        result = check_frontier(path, data, schema, domains, shapes, today)
        errors, warnings = result[0], result[1]
        overdue = result[2] if len(result) > 2 else False
        all_errors += errors
        all_warnings += warnings
        overdue_count += overdue
        if isinstance(data, dict) and "id" in data:
            if data["id"] in ids:
                all_errors.append(f"duplicate frontier id '{data['id']}' in {path} and {ids[data['id']]}")
            ids[data["id"]] = path

    for w in all_warnings:
        print(f"WARNING {w}")
    for e in all_errors:
        print(f"ERROR   {e}")
    print(f"\nChecked {len(files)} frontier(s): {len(all_errors)} error(s), {len(all_warnings)} warning(s), {overdue_count} overdue.")

    if all_errors or (args.strict and overdue_count):
        sys.exit(1)


if __name__ == "__main__":
    main()
