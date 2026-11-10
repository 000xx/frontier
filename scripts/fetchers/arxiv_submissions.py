"""Discovery stub: probes arXiv statistics endpoints."""
from . import common

FRONTIER = "data/frontiers/knowledge/arxiv-submissions.yaml"
URLS = [
    "https://arxiv.org/stats/monthly_submissions",
    "http://export.arxiv.org/api/query?search_query=submittedDate:[202001010000+TO+202001312359]&max_results=0",
]


def fetch():
    for url in URLS:
        try:
            raw = common.get(url).decode("utf-8", "replace")
            print(f"DIAG {url} bytes={len(raw)}")
            print("DIAG head: " + " ".join(raw[:1500].split()))
        except common.SourceError as exc:
            print(f"DIAG {url}: {exc}")
    raise common.SourceError("discovery run")
