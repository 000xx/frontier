"""Discovery stub: prints CSV links on the arXiv monthly submissions page and tries them."""
import re

from . import common

FRONTIER = "data/frontiers/knowledge/arxiv-submissions.yaml"
URL = "https://arxiv.org/stats/monthly_submissions"


def fetch():
    raw = common.get(URL).decode("utf-8", "replace")
    for m in re.finditer(r"<a[^>]*href=\"([^\"]*)\"[^>]*>(.*?)</a>", raw, flags=re.S | re.I):
        if "csv" in (m.group(1) + m.group(2)).lower() or "download" in m.group(2).lower():
            print(f"DIAG link: {m.group(1)} text={' '.join(re.sub(r'<[^>]+>', ' ', m.group(2)).split())}")
    for m in re.finditer(r"csv[^\"' ]*", raw, flags=re.I):
        print(f"DIAG csvref: {m.group(0)[:200]}")
    raise common.SourceError("discovery run")
