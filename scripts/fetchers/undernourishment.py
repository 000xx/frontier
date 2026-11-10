"""Discovery stub: prints the OWID CSV for prevalence of undernourishment."""
from . import common

FRONTIER = "data/frontiers/food/undernourishment.yaml"
URL = "https://ourworldindata.org/grapher/prevalence-of-undernourishment.csv?country=OWID_WRL"


def fetch():
    raw = common.get(URL).decode("utf-8-sig")
    lines = raw.splitlines()
    print(f"DIAG lines={len(lines)} head={lines[0]}")
    for line in lines:
        if line.startswith("World,OWID_WRL"):
            print(f"DIAG row: {line}")
    raise common.SourceError("discovery run")
