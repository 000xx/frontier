"""Discovery stub: prints the OWID CSVs for candidate slugs."""
from . import common

FRONTIER = "data/frontiers/food/cereal-yields.yaml"
SLUGS = ["cereal-yield", "cereal-yields-tonnes-per-hectare", "crop-yields"]


def fetch():
    for slug in SLUGS:
        try:
            raw = common.get(f"https://ourworldindata.org/grapher/{slug}.csv?country=OWID_WRL").decode("utf-8-sig")
        except common.SourceError as exc:
            print(f"DIAG {slug}: {exc}")
            continue
        lines = raw.splitlines()
        print(f"DIAG {slug} lines={len(lines)} head={lines[0]}")
        for line in lines:
            if line.startswith("World,OWID_WRL"):
                print(f"DIAG row: {line}")
    raise common.SourceError("discovery run")
