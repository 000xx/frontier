#!/usr/bin/env python3
"""Refresh frontiers from their machine-readable sources.

Runs every fetcher in scripts/fetchers/ (or the ones named with --only), checks what
changed, validates the result, and writes a report. Used by the scheduled
"Refresh data" GitHub Actions workflow; it can also be run by hand.

  python scripts/refresh.py                        # all fetchers
  python scripts/refresh.py --only erdos_problems  # one fetcher

Safety rules:
- A fetcher that fails, or whose output fails validation, has all its file changes
  reverted. It is reported as a failure and nothing from it is kept.
- A change that removes existing entries, or changes many existing values at once, is
  marked "needs review" so it is not merged automatically.
- update.last_checked is set when a fetch succeeds and either the data changed or the
  date is at least a week old, so the history isn't flooded with date-only commits.
"""
import argparse
import datetime as dt
import importlib
import json
import pkgutil
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetchers  # noqa: E402
from fetchers import common  # noqa: E402

BLOCKS = {
    "records": lambda e: (e.get("series"), str(e.get("date")), e.get("holder")),
    "observations": lambda e: (e.get("series"), str(e.get("date"))),
    "items": lambda e: e.get("id"),
    "candidates": lambda e: e.get("id"),
}
CHANGE_LIMIT = 0.10   # share of existing entries that may change before review is needed
CHANGE_FLOOR = 5      # always allow at least this many changed entries


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def dirty_paths():
    out = git("status", "--porcelain", "--untracked-files=all")
    return {line[3:].strip() for line in out.splitlines() if line.strip()}


def revert(paths):
    tracked = [p for p in paths if git("ls-files", "--error-unmatch", p).strip()]
    untracked = [p for p in paths if p not in tracked]
    if tracked:
        subprocess.run(["git", "checkout", "--", *tracked], cwd=ROOT, check=False)
    for p in untracked:
        (ROOT / p).unlink(missing_ok=True)


def compare(before, after):
    """Count added, removed and changed entries across the data blocks."""
    added = removed = changed = existing = 0
    for block, key in BLOCKS.items():
        old = {key(e): e for e in before.get(block) or []}
        new = {key(e): e for e in after.get(block) or []}
        existing += len(old)
        added += len(set(new) - set(old))
        removed += len(set(old) - set(new))
        changed += sum(1 for k in set(old) & set(new) if old[k] != new[k])
    return {"added": added, "removed": removed, "changed": changed, "existing": existing}


def validation_errors():
    result = subprocess.run([sys.executable, "scripts/validate.py"], cwd=ROOT,
                            capture_output=True, text=True)
    return [l for l in result.stdout.splitlines() if l.startswith("ERROR")] if result.returncode else []


def needs_last_checked(frontier_path):
    data = common.load(frontier_path)
    last = dt.date.fromisoformat(str(data["update"]["last_checked"]))
    return (dt.date.today() - last).days >= 7


def available_fetchers():
    return sorted(m.name for m in pkgutil.iter_modules(fetchers.__path__) if m.name != "common" and not m.name.startswith("_"))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", default="", help="comma-separated fetcher names")
    parser.add_argument("--report", default="refresh-report.md")
    parser.add_argument("--outcome", default="refresh-outcome.json")
    args = parser.parse_args()

    names = [n.strip() for n in args.only.split(",") if n.strip()] or available_fetchers()
    unknown = set(names) - set(available_fetchers())
    if unknown:
        sys.exit(f"unknown fetchers: {', '.join(sorted(unknown))}")
    if dirty_paths():
        sys.exit("the working tree has uncommitted changes; refresh needs a clean checkout")

    results = []
    for name in names:
        mod = importlib.import_module(f"fetchers.{name}")
        before = common.load(mod.FRONTIER)
        start = dirty_paths()
        entry = {"fetcher": name, "frontier": mod.FRONTIER, "messages": [], "state": "unchanged"}
        try:
            messages = mod.fetch() or []
            diff = compare(before, common.load(mod.FRONTIER))
            data_changed = bool(messages) or any(diff[k] for k in ("added", "removed", "changed"))
            if data_changed or needs_last_checked(mod.FRONTIER):
                common.set_last_checked(mod.FRONTIER)
            errors = validation_errors()
            if errors:
                raise RuntimeError("validation failed after refresh:\n" + "\n".join(errors[:20]))
            entry["messages"] = messages
            entry["diff"] = diff
            if data_changed:
                limit = max(CHANGE_FLOOR, int(diff["existing"] * CHANGE_LIMIT))
                review = []
                if diff["removed"]:
                    review.append(f"{diff['removed']} existing entries removed")
                # Sources that refit their whole history (REVISES_PAST) change many values at
                # once by design; removals still need review.
                if diff["changed"] > limit and not getattr(mod, "REVISES_PAST", False):
                    review.append(f"{diff['changed']} existing entries changed (limit {limit})")
                entry["state"] = "review" if review else "changed"
                entry["review_reasons"] = review
            elif dirty_paths() - start:
                entry["state"] = "checked"
        except Exception as exc:  # noqa: BLE001
            revert(dirty_paths() - start)
            entry["state"] = "failed"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["traceback"] = traceback.format_exc(limit=3)
        results.append(entry)

    lines = [f"# Data refresh, {common.today()}", ""]
    for state, title in [("review", "Needs review"), ("changed", "Updated"), ("failed", "Failed"),
                         ("checked", "Checked, no new data"), ("unchanged", "No change")]:
        group = [r for r in results if r["state"] == state]
        if not group:
            continue
        lines += [f"## {title}", ""]
        for r in group:
            lines.append(f"- **{r['fetcher']}** (`{r['frontier']}`)")
            for m in r.get("messages", [])[:40]:
                lines.append(f"  - {m}")
            if len(r.get("messages", [])) > 40:
                lines.append(f"  - ... and {len(r['messages']) - 40} more")
            if r.get("diff") and state in ("review", "changed"):
                d = r["diff"]
                lines.append(f"  - entries: {d['added']} added, {d['changed']} changed, {d['removed']} removed")
            for reason in r.get("review_reasons", []):
                lines.append(f"  - needs review: {reason}")
            if r.get("error"):
                lines.append(f"  - error: {r['error'].splitlines()[0][:300]}")
        lines.append("")
    Path(args.report).write_text("\n".join(lines), encoding="utf-8")

    outcome = {
        "changed": [r["fetcher"] for r in results if r["state"] in ("changed", "review", "checked")],
        "review": [r["fetcher"] for r in results if r["state"] == "review"],
        "failed": [r["fetcher"] for r in results if r["state"] == "failed"],
        "data_changed": [r["fetcher"] for r in results if r["state"] in ("changed", "review")],
    }
    Path(args.outcome).write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    print("\n".join(lines))
    for r in results:
        if r.get("traceback"):
            print(f"--- {r['fetcher']} traceback ---\n{r['traceback']}")


if __name__ == "__main__":
    main()
