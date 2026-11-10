# Frontier

The frontier of science and technology, in numbers. This repository is the data backend: every tracked frontier, its records, its sources, and the papers and news that explain it.

## Layout

```
data/
  domains.yaml          the 22 domains and their subfields
  chart-shapes.yaml     the chart shapes a frontier can use
  frontiers/<domain>/<frontier-id>.yaml   one file per frontier
  datasets/<dataset-id>/                  copies of source datasets, with a NOTICE for each
schema/frontier.schema.json              the format every frontier file must follow
scripts/validate.py                      checks every file; run before committing
scripts/import_*.py                      rebuild a frontier's records from its dataset
```

## What a frontier file holds

| Field | What it is |
| --- | --- |
| `metric` | What is measured, its unit, which direction is progress, and any hard limit or target |
| `chart` | The primary chart shape and any secondary ones |
| `series` | Named lines on the chart, such as one per technology |
| `sources` | Where the data comes from; one is marked `primary` |
| `records` | Record results as published by the source, with date, holder, conditions, status and source |
| `events` | Progress that doesn't move the number: papers, milestones, setbacks, retractions |
| `reading` | The "start here" ladder: 5 minutes, 1 hour, deep |
| `update` | How often to check, and when it was last checked |

Every record carries a status: `claimed`, `peer_reviewed`, `confirmed` or `retracted`. Nothing reaches the site without a source.

## Data credits

Each dataset folder has a NOTICE.md with its source's terms and the credit line the site must show. Solar cell records: data courtesy of the National Laboratory of the Rockies (U.S. Department of Energy / NLR / Alliance for Energy Innovation).

## How updates work

1. A scheduled update run checks each frontier whose cadence is due, starting with its primary source.
2. It opens a pull request with new records and events, each linked to its source. It never pushes to `main` directly.
3. The validation check runs on the pull request.
4. A human reviews and merges. Merging is the moment a record becomes public.

Even when nothing changed, the run updates `last_checked`, so the site can show how fresh each frontier is. The weekly validation run lists frontiers that are overdue.

## Run the checks locally

```
pip install -r requirements.txt
python scripts/validate.py
```

## Adding a frontier

Copy an existing file into `data/frontiers/<domain>/`, rename it to the new id, and fill it in. New frontiers start as `status: draft` and go `live` once their record history and reading list are complete.

The full list of planned frontiers and the build order are in the planning doc.

## The site

The public site is in `site/`: one page (`index.html`), a stylesheet, a script that draws the pages and charts (`js/app.js`) and a photo. It reads everything from `site/js/data.js`, which is generated and not committed.

- Build the data file: `python scripts/build_site_data.py`, then open `site/index.html` in a browser.
- Every file under `data/frontiers/` becomes a page. Nothing in `site/` needs to change when a frontier is added or updated.
- `site/config.json` holds the choices that are not data: the site name, which series each frontier features on the front page, and the "next in the queue" list.
- The `Publish site` workflow rebuilds the data file and publishes `site/` to GitHub Pages on every push to `main`. In the repository settings, Pages must have its source set to "GitHub Actions".
- Only the record chart shape is drawn so far. A frontier whose primary shape is something else still gets a record chart until that shape is built.
