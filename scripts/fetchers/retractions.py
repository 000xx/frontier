"""Discovery stub: prints the end of the Retraction Watch README and yearly counts of retraction notices."""
import csv
import io
import re
from collections import Counter

from . import common

FRONTIER = "data/frontiers/knowledge/retractions.yaml"
BASE = "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/"


def fetch():
    raw = common.get(BASE + "README.md").decode("utf-8", "replace")
    flat = " ".join(raw.split())
    print("DIAG readme end: " + flat[-1300:])
    data = common.get(BASE + "retraction_watch.csv").decode("utf-8-sig", "replace")
    rows = list(csv.DictReader(io.StringIO(data)))
    years = Counter()
    for r in rows:
        if r["RetractionNature"] != "Retraction":
            continue
        m = re.search(r"(\d{4})", r["RetractionDate"])
        if m:
            years[m.group(1)] += 1
    print("DIAG retraction-only: " + " ".join(f"{y}={years[y]}" for y in sorted(years) if y >= "1990"))
    raise common.SourceError("discovery run")
