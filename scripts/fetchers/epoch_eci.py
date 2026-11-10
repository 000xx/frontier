"""Refresh the AI capabilities index frontier from Epoch AI's ECI scores (CC BY 4.0).

Downloads https://epoch.ai/data/eci_scores.csv, checks it still looks like the file the
importer was written for, stores it unchanged in data/datasets/epoch-eci/ and rebuilds the
frontier's records with scripts/import_epoch_eci.py.

Epoch refits every score when new results arrive, so past values move a little between
versions. REVISES_PAST tells refresh.py that changed values are expected; removed records
(a model that no longer holds the frontier after a refit) still go to review.
"""
import csv
import io

from . import common

FRONTIER = "data/frontiers/ai/ai-capabilities-index.yaml"
DATASET = "data/datasets/epoch-eci"
URL = "https://epoch.ai/data/eci_scores.csv"
REVISES_PAST = True
HEADER = ["Model", "Display name", "eci", "eci_ci_low", "eci_ci_high", "date", "Organization",
          "Country (of organization)", "Model accessibility", "Accessibility group", "model_versions"]
MIN_ROWS = 200  # 255 rows on 2026-11-09; far fewer means the file was cut short or replaced


def check(raw):
    text = raw.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or rows[0] != HEADER:
        raise common.SourceError(f"unexpected header in {URL}: {rows[0] if rows else 'empty file'}")
    body = [dict(zip(HEADER, r)) for r in rows[1:] if any(r)]
    if len(body) < MIN_ROWS:
        raise common.SourceError(f"only {len(body)} models in {URL} (expected at least {MIN_ROWS})")
    for r in body:
        try:
            float(r["eci"])
        except ValueError:
            raise common.SourceError(f"non-numeric score for {r['Model']!r}: {r['eci']!r}") from None
        if len(r["date"]) != 10:
            raise common.SourceError(f"unexpected date for {r['Model']!r}: {r['date']!r}")
    return body


def fetch():
    raw = common.get(URL)
    body = check(raw)
    before = {(r["series"], r["holder"]) for r in common.load(FRONTIER).get("records", [])}
    if not common.write_if_changed(f"{DATASET}/eci_scores.csv", raw):
        return []
    readme = f"{DATASET}/README.md"
    common.set_readme_row(readme, "Retrieved", common.today())
    common.set_readme_row(readme, "eci_scores.csv SHA-256", common.sha256(raw))
    common.run_script("scripts/import_epoch_eci.py")
    after = common.load(FRONTIER).get("records", [])
    new = [r for r in after if (r["series"], r["holder"]) not in before]
    messages = [f"New ECI file ({len(body)} models)"]
    messages += [f"New frontier model in {r['series']}: {r['holder']} at {r['value']} ({r['date']})"
                 for r in new]
    return messages
