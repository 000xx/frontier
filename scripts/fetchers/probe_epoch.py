"""Temporary probe: print the shape of Epoch AI's ECI files. Never changes data."""
import csv, io, zipfile
from . import common

FRONTIER = "data/frontiers/ai/ai-task-horizon.yaml"

def fetch():
    raw = common.get("https://epoch.ai/data/eci_scores.csv")
    text = raw.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    print("ECI rows:", len(rows) - 1)
    print("HEADER:", rows[0])
    for r in rows[1:6]:
        print("ROW:", r)
    print("SHA", common.sha256(raw))
    z = zipfile.ZipFile(io.BytesIO(common.get("https://epoch.ai/data/benchmark_data.zip")))
    for i in z.infolist():
        print("ZIP:", i.filename, i.file_size)
    raise common.SourceError("probe only")
