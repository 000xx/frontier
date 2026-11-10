#!/usr/bin/env python3
"""Rebuild the items and database observations of the erdos-problems frontier.

Reads data/datasets/erdos-problems/problems.csv and statistics_history.csv and rewrites
the `items` block, and the observations that cite the database, in
data/frontiers/mathematics/erdos-problems.yaml. Every other field is kept, including
observations from other sources.

AI involvement comes from Terence Tao's "AI contributions to Erdős problems" wiki, which
stopped being updated on 2026-06-30. Its text is not copied into this repository. To
refresh it, download the page's markdown and pass its path:

  curl -o /tmp/ai-wiki.md \
    "https://raw.githubusercontent.com/wiki/teorth/erdosproblems/AI-contributions-to-Erd%C5%91s-problems.md"
  python scripts/import_erdos_problems.py --ai-wiki /tmp/ai-wiki.md

Without --ai-wiki, the ai_involvement and note already on each item are kept.

Mapping rules:
- status: proved, disproved, solved and independent (of ZFC) count as done, matching the
  database's own solved count; every other state (open, falsifiable, verifiable, decidable,
  not provable, not disprovable, and "open (Lean)") counts as open. status_detail keeps the
  database's combined status word verbatim.
- ai_involvement: the wiki's Section 1 lists contributions where AI played a primary role
  and Section 2 those where it played a secondary role. An item is `primary` if it has a
  Section 1 row rated full or partial (green or yellow), otherwise `assisted` if it has a
  Section 2 row that is not rated incorrect or unverified (red or white). Rows that are only
  incorrect or unverified are not counted.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import load_yaml  # noqa: E402  (keeps dates as strings)

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "data" / "datasets" / "erdos-problems"
FRONTIER_PATH = ROOT / "data" / "frontiers" / "mathematics" / "erdos-problems.yaml"
DB_SOURCE = "erdos-database"
WIKI_SOURCE = "ai-contributions-wiki"

DONE_STATES = {"proved", "disproved", "solved", "independent"}
NOT_NAMES = {"ambiguous statement", "literature review sought", "partial r=2 result"}
SECTION_NAMES = {
    "1a": "AI standalone",
    "1b": "AI alongside literature",
    "1c": "AI building on literature",
    "1d": "AI collaborating with humans",
    "2a": "literature search",
    "2b": "formalization",
    "2c": "rewriting",
    "2d": "computation",
}
# Index of the outcome column in each section's table (problem is column 0); None = no outcome column.
OUTCOME_COL = {"1a": 3, "1b": 3, "1c": 4, "1d": 4, "2a": 3, "2b": None, "2c": None, "2d": None}
GOOD = ("🟢", "🟡")  # full or partial; 🔴 incorrect and ⚪ unverified rows are not counted


def parse_ai_wiki(path):
    """Return {problem number: [(section, outcome mark or '', date text), ...]}."""
    rows, section = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^###\s+(\d)\((\w)\)\.", line)
        if m:
            section = m.group(1) + m.group(2)
            continue
        if section is None or not line.startswith("| [["):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        problems = re.findall(r"\[\[(\d+)\]\]", cells[0])
        col = OUTCOME_COL[section]
        outcome = cells[col] if col is not None and col < len(cells) else ""
        date_col = {"1d": 3, "2b": 3}.get(section, 2)
        date = cells[date_col] if date_col < len(cells) else ""
        for num in problems:
            rows.setdefault(num, []).append((section, outcome, date))
    return rows


def classify(entries):
    """Return (ai_involvement or None, note or None) for one problem's wiki rows."""
    def counts(section, outcome):
        if OUTCOME_COL[section] is None:
            return True
        return any(g in outcome for g in GOOD)

    primary = [e for e in entries if e[0].startswith("1") and counts(*e[:2])]
    secondary = [e for e in entries if e[0].startswith("2") and counts(*e[:2])]
    if primary:
        level, used = "primary", primary
    elif secondary:
        level, used = "assisted", secondary
    else:
        return None, "AI wiki lists only AI attempts rated incorrect or unverified."
    parts = []
    for section, outcome, date in used:
        mark = ("full" if "🟢" in outcome else "partial" if "🟡" in outcome else "")
        label = f"{section[0]}({section[1]}) {SECTION_NAMES[section]}"
        parts.append(f"{label}, {date}" + (f", {mark}" if mark else ""))
    return level, "AI wiki (as of 2026-06-30): " + "; ".join(parts) + "."


def build_items(ai_rows, previous):
    with open(DATASET / "problems.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    items = []
    for r in rows:
        num = r["number"]
        comment = r["comments"].strip()
        tags = [t for t in r["tags"].split(";") if t]
        label = f"Problem {num}"
        if comment and comment not in NOT_NAMES:
            label += f" ({comment})"
        item = {"id": num, "label": label}
        if tags:
            item["group"] = tags[0]
        item["status"] = "done" if r["informal_status"] in DONE_STATES else "open"
        item["status_detail"] = r["status"]
        notes = []
        if ai_rows is not None:
            level, note = classify(ai_rows[num]) if num in ai_rows else (None, None)
            if level:
                item["ai_involvement"] = level
            if note:
                notes.append(note)
        else:
            prev = previous.get(num, {})
            if prev.get("ai_involvement"):
                item["ai_involvement"] = prev["ai_involvement"]
            old = prev.get("note", "")
            notes += [n.strip() + "." for n in old.split(".") if n.strip().startswith("AI wiki")]
        if comment == "ambiguous statement":
            notes.append("The database marks the statement as ambiguous.")
        item["url"] = f"https://www.erdosproblems.com/{num}"
        item["source"] = DB_SOURCE
        if notes:
            item["note"] = " ".join(notes)
        items.append(item)
    return items


def build_observations():
    """One point per month (the last database commit in that month): solved and total problems."""
    with open(DATASET / "statistics_history.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    by_month = {}
    for r in rows:
        if not r.get("total_solved"):
            continue
        by_month[r["date"][:7]] = r  # rows are in commit order, so the last one wins
    obs = []
    for month in sorted(by_month):
        r = by_month[month]
        day = r["date"][:10]
        commit = r["commit"][:7]
        obs.append({"date": day, "value": int(r["total_solved"]), "series": "solved",
                    "source": DB_SOURCE, "note": f"Database commit {commit}"})
        obs.append({"date": day, "value": int(r["total_problems"]), "series": "total",
                    "source": DB_SOURCE, "note": f"Database commit {commit}"})
    return obs


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ai-wiki", help="path to the downloaded AI-contributions wiki markdown")
    args = parser.parse_args()

    data = load_yaml(FRONTIER_PATH)
    source_ids = {s["id"] for s in data["sources"]}
    for sid in (DB_SOURCE, WIKI_SOURCE):
        if sid not in source_ids:
            sys.exit(f"{FRONTIER_PATH} needs a source with id '{sid}'")

    previous = {i["id"]: i for i in data.get("items", [])}
    ai_rows = parse_ai_wiki(args.ai_wiki) if args.ai_wiki else None
    data["items"] = build_items(ai_rows, previous)
    others = [o for o in data.get("observations", []) if o["source"] != DB_SOURCE]
    data["observations"] = build_observations() + others

    with open(FRONTIER_PATH, "w", encoding="utf-8") as f:
        f.write("# Items and the database observations are generated by scripts/import_erdos_problems.py.\n")
        f.write("# Edit the other fields by hand; edit the dataset, not the items, for status changes.\n")
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=100)
    items = data["items"]
    done = sum(i["status"] == "done" for i in items)
    ai = sum("ai_involvement" in i for i in items)
    print(f"Wrote {len(items)} items ({done} done, {ai} with AI involvement) and "
          f"{len(data['observations'])} observations to {FRONTIER_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
