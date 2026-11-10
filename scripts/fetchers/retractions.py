"""Discovery stub: reads the Retraction Watch CSV and README from Crossref's GitLab repository."""
import csv
import io
from collections import Counter

from . import common

FRONTIER = "data/frontiers/knowledge/retractions.yaml"
BASE = "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/"


def fetch():
    for name in ["README.md", "LICENSE", "LICENSE.md"]:
        try:
            raw = common.get(BASE + name).decode("utf-8", "replace")
            print(f"DIAG {name} bytes={len(raw)}")
            print("DIAG text: " + " ".join(raw[:1200].split()))
        except common.SourceError as exc:
            print(f"DIAG {name}: {exc}")
    raw = common.get(BASE + "retraction_watch.csv").decode("utf-8-sig", "replace")
    rows = list(csv.DictReader(io.StringIO(raw)))
    print(f"DIAG csv rows={len(rows)} columns={list(rows[0].keys()) if rows else None}")
    years = Counter(r.get("RetractionDate", "")[-4:] for r in rows)
    for y in sorted(years):
        print(f"DIAG year {y}: {years[y]}")
    raise common.SourceError("discovery run")
