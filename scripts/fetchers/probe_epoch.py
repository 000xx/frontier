"""Temporary probe: print Epoch AI's ECI scores file as base64. Never changes data."""
import base64
from . import common
FRONTIER = "data/frontiers/ai/ai-task-horizon.yaml"

def fetch():
    raw = common.get("https://epoch.ai/data/eci_scores.csv")
    print("SHA", common.sha256(raw))
    b = base64.b64encode(raw).decode()
    for i in range(0, len(b), 4000):
        print("B64", b[i:i+4000])
    raise common.SourceError("probe only")
