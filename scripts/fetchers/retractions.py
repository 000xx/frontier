"""Discovery stub: reads the Retraction Watch README tail, a sample date and yearly counts from Crossref's GitLab repo."""
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
    print("DIAG readme tail: " + flat[1100:2600])
    data = common.get(BASE + "retraction_watch.csv").decode("utf-8-sig", "replace")
    rows = list(csv.DictReader(io.StringIO(data)))
    print("DIAG sample dates: " + " | ".join(r["RetractionDate"] for r in rows[:3]) + " | nature: " + " | ".join(r["RetractionNature"] for r in rows[:3]))
    years = Counter()
    nature = Counter()
    for r in rows:
        m = re.search(r"(\d{4})", r["RetractionDate"])
        years[m.group(1) if m else "none"] += 1
        nature[r["RetractionNature"]] += 1
    for y in sorted(years):
        print(f"DIAG year {y}: {years[y]}")
    for k, v in nature.most_common(8):
        print(f"DIAG nature {k!r}: {v}")
    raise common.SourceError("discovery run")
