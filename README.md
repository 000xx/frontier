# Frontier

The frontier of science and technology, in numbers. This repository is the data backend: every tracked frontier, its records, its sources, and the papers and news that explain it.

## Layout

```
data/
  domains.yaml          the 22 domains and their subfields
  chart-shapes.yaml     the chart shapes a frontier can use
  frontiers/<domain>/<frontier-id>.yaml   one file per frontier
schema/frontier.schema.json              the format every frontier file must follow
scripts/validate.py                      checks every file; run before committing
```

## What a frontier file holds

| Field | What it is |
| --- | --- |
| `metric` | What is measured, its unit, which direction is progress, and any hard limit or target |
| `chart` | The primary chart shape and any secondary ones |
| `series` | Named lines on the chart, such as one per technology |
| `sources` | Where the data comes from; one is marked `primary` |
| `records` | Every value that set a new best, with date, holder, conditions, status and source |
| `events` | Progress that doesn't move the number: papers, milestones, setbacks, retractions |
| `reading` | The "start here" ladder: 5 minutes, 1 hour, deep |
| `update` | How often to check, and when it was last checked |

Every record carries a status: `claimed`, `peer_reviewed`, `confirmed` or `retracted`. Nothing reaches the site without a source.

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
