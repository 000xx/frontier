"""Discovery stub: prints yearly sums of the arXiv monthly submissions CSV."""
import csv
import io
from collections import defaultdict

from . import common

FRONTIER = "data/frontiers/knowledge/arxiv-submissions.yaml"
URL = "https://arxiv.org/stats/get_monthly_submissions"


def fetch():
    raw = common.get(URL).decode("utf-8", "replace")
    sums = defaultdict(int)
    months = defaultdict(int)
    for row in csv.DictReader(io.StringIO(raw)):
        y = row["month"][:4]
        sums[y] += int(row["submissions"])
        months[y] += 1
    for y in sorted(sums):
        print(f"DIAG {y} months={months[y]} sum={sums[y]}")
    raise common.SourceError("discovery run")
