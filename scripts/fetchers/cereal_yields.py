"""Discovery stub: prints the OWID CSV for world cereal yields."""
from . import common

FRONTIER = "data/frontiers/food/cereal-yields.yaml"
URL = "https://ourworldindata.org/grapher/cereal-yields.csv?country=OWID_WRL"


def fetch():
    raw = common.get(URL).decode("utf-8-sig")
    lines = raw.splitlines()
    print(f"DIAG lines: {len(lines)}")
    for line in lines[:3]:
        print(f"DIAG head: {line}")
    for line in lines:
        if line.startswith("World,") or line.startswith("Entity,"):
            print(f"DIAG row: {line}")
    raise common.SourceError("discovery run")
