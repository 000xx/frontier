"""Probe version: lists Epoch's benchmark_data.zip members and the FrontierMath file header."""
import csv
import io
import zipfile

from . import common

FRONTIER = "data/frontiers/ai/frontiermath.yaml"
URL = "https://epoch.ai/data/benchmark_data.zip"


def fetch():
    raw = common.get(URL)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    print(f"DIAG {len(names)} members: {names}")
    for name in names:
        if "frontiermath" in name.lower() or "frontier_math" in name.lower():
            text = zf.read(name).decode("utf-8-sig")
            rows = list(csv.reader(io.StringIO(text)))
            print(f"DIAG {name}: {len(rows) - 1} rows; header {rows[0]}")
    raise common.SourceError("probe only")
