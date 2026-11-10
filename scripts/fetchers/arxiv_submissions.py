"""Discovery stub: prints the arXiv monthly submissions CSV."""
from . import common

FRONTIER = "data/frontiers/knowledge/arxiv-submissions.yaml"
URL = "https://arxiv.org/stats/get_monthly_submissions"


def fetch():
    raw = common.get(URL).decode("utf-8", "replace")
    lines = raw.splitlines()
    print(f"DIAG lines={len(lines)} bytes={len(raw)}")
    for line in lines[:4]:
        print(f"DIAG head: {line}")
    for line in lines[-3:]:
        print(f"DIAG tail: {line}")
    raise common.SourceError("discovery run")
