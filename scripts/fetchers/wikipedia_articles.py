"""Discovery stub: probes Wikimedia endpoints for article counts."""
from . import common

FRONTIER = "data/frontiers/knowledge/wikipedia-articles.yaml"
URLS = [
    "https://en.wikipedia.org/w/api.php?action=query&meta=siteinfo&siprop=statistics&format=json",
    "https://stats.wikimedia.org/EN/TablesWikipediaEN.htm",
    "https://stats.wikimedia.org/EN/TablesWikipediaZZ.htm",
]


def fetch():
    for url in URLS:
        try:
            raw = common.get(url).decode("utf-8", "replace")
            print(f"DIAG {url} bytes={len(raw)}")
            print("DIAG head: " + " ".join(raw[:600].split()))
        except common.SourceError as exc:
            print(f"DIAG {url}: {exc}")
    raise common.SourceError("discovery run")
