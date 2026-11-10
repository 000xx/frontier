"""Discovery stub: prints the table of the arXiv monthly submissions page."""
import re

from . import common

FRONTIER = "data/frontiers/knowledge/arxiv-submissions.yaml"
URL = "https://arxiv.org/stats/monthly_submissions"


def fetch():
    raw = common.get(URL).decode("utf-8", "replace")
    tables = re.findall(r"<table.*?</table>", raw, flags=re.S | re.I)
    print(f"DIAG tables: {len(tables)}")
    for t in tables:
        text = re.sub(r"<[^>]+>", " ", t)
        print("DIAG table: " + " ".join(text.split())[:6000])
    raise common.SourceError("discovery run")
