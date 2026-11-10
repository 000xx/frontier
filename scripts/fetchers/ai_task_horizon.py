"""Refresh the "TH1.1 after the March 2026 correction" series of the AI task-horizon frontier.

Source: METR's agent results file benchmark_results_1_1.yaml, linked from
https://metr.org/time-horizons/. For each model it gives the 50% time horizon and its
confidence interval, in minutes, after the 3 March 2026 fit correction. Only that series is
written; the older series are left alone. Existing records are never changed: a model already
recorded is checked, and the run fails if its value now differs.
"""
import datetime as dt
import json
import math
import re

import yaml

from . import common

FRONTIER = "data/frontiers/ai/ai-task-horizon.yaml"
SERIES = "th1-1-corrected"
SOURCE = "metr-time-horizons"
URL = "https://metr.org/assets/benchmark_results_1_1.yaml"
BENCHMARK = "METR-Horizon-v1.1"
# METR says results above about 16 hours are unreliable with this task suite, so they are not
# recorded automatically. They are printed to the log for the owner to decide on.
RELIABLE_LIMIT_MINUTES = 16 * 60
# The file had 26 entries when this fetcher was written. Fewer than this means something was removed.
MIN_ENTRIES = 26

# METR's keys in the file -> model names as METR writes them (its release-date file and posts).
NAMES = {
    "claude_3_5_sonnet_20240620_inspect": "Claude 3.5 Sonnet (Old)",
    "claude_3_5_sonnet_20241022_inspect": "Claude 3.5 Sonnet (New)",
    "claude_3_7_sonnet_inspect": "Claude 3.7 Sonnet",
    "claude_3_opus_inspect": "Claude 3 Opus",
    "claude_4_1_opus_inspect": "Claude 4.1 Opus",
    "claude_4_opus_inspect": "Claude 4 Opus",
    "claude_opus_4_5_inspect": "Claude Opus 4.5",
    "claude_opus_4_6_inspect": "Claude Opus 4.6",
    "claude_mythos_preview_early_inspect": "Claude Mythos Preview (early)",
    "davinci_002": "davinci-002 (GPT-3)",
    "gemini_3_pro": "Gemini 3 Pro",
    "gemini_3_1_pro": "Gemini 3.1 Pro",
    "gpt2": "GPT-2",
    "gpt_3_5_turbo_instruct": "gpt-3.5-turbo-instruct",
    "gpt_4": "GPT-4 0314",
    "gpt_4_1106_inspect": "GPT-4 1106",
    "gpt_4_turbo_inspect": "GPT-4 Turbo",
    "gpt_4o_inspect": "GPT-4o",
    "gpt_5_1_codex_max_inspect": "GPT-5.1-Codex-Max",
    "gpt_5_2": "GPT-5.2",
    "gpt_5_2025_08_07_inspect": "GPT-5",
    "gpt_5_3_codex": "GPT-5.3-Codex",
    "gpt_5_4": "GPT-5.4",
    "o1_inspect": "o1",
    "o1_preview": "o1-preview",
    "o3_inspect": "o3",
}


def _number(value, what):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise common.SourceError(f"{what} is not a positive number: {value!r}")
    return float(value)


def _parse(key, entry):
    if key not in NAMES:
        raise common.SourceError(f"no model name for METR entry '{key}'; add it to NAMES")
    if not isinstance(entry, dict) or not isinstance(entry.get("release_date"), dt.date):
        raise common.SourceError(f"{key}: no release_date")
    p50 = (entry.get("metrics") or {}).get("p50_horizon_length")
    if not isinstance(p50, dict):
        raise common.SourceError(f"{key}: no p50_horizon_length")
    est = _number(p50.get("estimate"), f"{key} estimate")
    low = _number(p50.get("ci_low"), f"{key} ci_low")
    high = _number(p50.get("ci_high"), f"{key} ci_high")
    if not low <= est <= high:
        raise common.SourceError(f"{key}: interval {low} to {high} does not contain estimate {est}")
    return {"date": entry["release_date"].isoformat(), "holder": NAMES[key],
            "value": est, "low": low, "high": high}


def _round(x):
    return float(f"{x:.3g}")  # three significant figures, as in the existing records


def _num(x):
    text = f"{x:.6f}".rstrip("0").rstrip(".")
    if "e" in text or "." not in text and not text.isdigit():
        raise common.SourceError(f"cannot write number {x!r}")
    return text


def _record_text(row):
    conditions = (f"TH1.1 task suite; METR's benchmark_results_1_1.yaml; fit after the 3 March 2026 "
                  f"correction; confidence interval [{_num(row['low'])}, {_num(row['high'])}] min")
    note = ("Claimed because it is METR's own estimate in its published agent results file, not a "
            "refereed paper. Date is the model's release_date in that file.")
    return "\n".join([
        f"- date: '{row['date']}'",
        f"  value: {_num(row['value'])}",
        f"  series: {SERIES}",
        f"  holder: {_quote(row['holder'])}",
        f"  conditions: {_quote(conditions)}",
        "  status: claimed",
        f"  source: {SOURCE}",
        f"  note: {_quote(note)}",
    ]) + "\n"


def _quote(text):
    # JSON strings are valid YAML double-quoted scalars.
    return json.dumps(text)


def fetch():
    raw = common.get(URL)
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise common.SourceError(f"could not parse {URL}: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("benchmark_name") != BENCHMARK or not isinstance(doc.get("results"), dict):
        raise common.SourceError("benchmark_results_1_1.yaml does not have the expected structure")
    results = doc["results"]
    if len(results) < MIN_ENTRIES:
        raise common.SourceError(f"only {len(results)} entries in the file; expected at least {MIN_ENTRIES}")

    parsed = [_parse(key, entry) for key, entry in results.items()]
    for row in parsed:
        row["value"] = _round(row["value"])
        row["low"] = _round(row["low"])
        row["high"] = _round(row["high"])

    data = common.load(FRONTIER)
    existing = {(r.get("series"), str(r["date"]), r["holder"]): r
                for r in data.get("records", []) if r.get("series") == SERIES}

    new = []
    for row in sorted(parsed, key=lambda r: (r["date"], r["holder"])):
        key = (SERIES, row["date"], row["holder"])
        if key in existing:
            old = existing[key]["value"]
            if float(old) != row["value"]:
                raise common.SourceError(
                    f"{row['holder']} ({row['date']}): recorded {old}, METR now gives {row['value']}; "
                    "existing records are not overwritten")
            continue
        if row["value"] > RELIABLE_LIMIT_MINUTES:
            print(f"not recorded (above METR's 16-hour reliability limit): {row['holder']} "
                  f"({row['date']}) {row['value']} min [{row['low']}, {row['high']}]")
            continue
        new.append(row)

    if not new:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    match = re.search(r"(?m)^events:", text)
    if not match:
        raise common.SourceError(f"{FRONTIER}: no events: block to insert records before")
    block = "".join(_record_text(row) for row in new)
    updated = text[:match.start()] + block + text[match.start():]
    path.write_text(updated, encoding="utf-8")

    # Check the written records parse and carry the values that were meant to be written.
    after = common.load(FRONTIER)
    written = {(r.get("series"), str(r["date"]), r["holder"]): r for r in after.get("records", [])}
    for row in new:
        rec = written.get((SERIES, row["date"], row["holder"]))
        if rec is None or float(rec["value"]) != row["value"]:
            raise common.SourceError(f"{row['holder']} ({row['date']}) did not write correctly")

    return [f"{row['holder']} ({row['date']}): 50% horizon {_num(row['value'])} min "
            f"[{_num(row['low'])}, {_num(row['high'])}]" for row in new]
