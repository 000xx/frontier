"""Discovery stub: prints OpenAlex open-access counts per publication year."""
import json

from . import common

FRONTIER = "data/frontiers/knowledge/open-access.yaml"
URL = ("https://api.openalex.org/works?filter=publication_year:{year},type:article"
       "&group_by=open_access.is_oa")


def fetch():
    for year in range(2000, 2026):
        raw = common.get(URL.format(year=year))
        data = json.loads(raw.decode("utf-8"))
        print(f"DIAG {year} total={data.get('meta', {}).get('count')} groups={json.dumps(data.get('group_by'))}")
    raise common.SourceError("discovery run")
