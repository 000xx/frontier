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
    doc = yaml.safe_load(raw)
    res = doc["results"]
    print("result entries:", len(res), "top keys:", sorted(doc.keys()))
    for key, e in res.items():
        m = e.get("metrics", {})
        p50 = m.get("p50_horizon_length")
        p80 = m.get("p80_horizon_length")
        extra = sorted(set(e.keys()) - {"benchmark_name", "metrics", "release_date", "scaffolds"})
        print(repr(key), "|", e.get("release_date"), "| p50", p50, "| p80", (p80 or {}).get("estimate"), "| sota", m.get("is_sota"), "| other", extra, "| metrics", sorted(m.keys()))
    rel = common.get(RELEASES_URL)
    print(rel.decode("utf-8", "replace"))
    return []
