"""Discovery fetcher for the GPU clusters frontier (Epoch AI data). Prints the header and sample rows."""
import csv
import io

from . import common

FRONTIER = "data/frontiers/ai/gpu-clusters.yaml"
URL = "https://epoch.ai/data/gpu_clusters.csv"


def fetch():
    raw = common.get(URL).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(raw))
    header = next(reader)
    rows = list(reader)
    print(f"DIAG rows {len(rows)}")
    print(f"DIAG header {header}")
    for r in rows[:2]:
        print(f"DIAG sample {[c[:80] for c in r]}")
    raise common.SourceError("discovery run: header printed, no parser yet")
