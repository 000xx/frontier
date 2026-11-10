"""Discovery stub: prints the text of the arXiv monthly submissions page."""
import re

from . import common

FRONTIER = "data/frontiers/knowledge/arxiv-submissions.yaml"
URL = "https://arxiv.org/stats/monthly_submissions"


def fetch():
    raw = common.get(URL).decode("utf-8", "replace")
    body = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    text = " ".join(re.sub(r"<[^>]+>", " ", body).split())
    print(f"DIAG len={len(text)} scripts={raw.count('<script')} div={raw.count('<div')} svg={raw.count('<svg')}")
    for i in range(0, min(len(text), 9000), 1500):
        print("DIAG text: " + text[i:i + 1500])
    raise common.SourceError("discovery run")
