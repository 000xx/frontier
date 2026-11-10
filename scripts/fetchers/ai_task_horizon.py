"""DIAGNOSTIC ONLY: print the structure of METR's benchmark_results_1_1.yaml. Writes nothing."""
import hashlib

import yaml

from . import common

FRONTIER = "data/frontiers/ai/ai-task-horizon.yaml"
YAML_URL = "https://metr.org/assets/benchmark_results_1_1.yaml"
RELEASES_URL = "https://raw.githubusercontent.com/METR/eval-analysis-public/main/data/external/release_dates.yaml"


def _show(label, obj, limit=1500):
    text = repr(obj)
    print(f"--- {label} ({type(obj).__name__}, {len(text)} chars) ---")
    print(text[:limit])


def fetch():
    raw = common.get(YAML_URL)
    print("bytes:", len(raw), "sha256:", hashlib.sha256(raw).hexdigest())
    print("head bytes:", repr(raw[:400]))
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        print("yaml parse error:", str(exc)[:500])
        return []
    _show("document", doc, 2500)
    if isinstance(doc, dict):
        for key, val in doc.items():
            _show(f"key {key!r}", val, 800)
    rel = common.get(RELEASES_URL)
    print("release dates bytes:", len(rel))
    print(rel[:600].decode("utf-8", "replace"))
    return []
