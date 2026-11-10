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
Erdős problems: data from the Erdős problems database (github.com/teorth/erdosproblems), Erdős problems database contributors, maintained by Thomas Bloom and Terence Tao; problems from erdosproblems.com.

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

The public site is in `site/` and is published with GitHub Pages. It reads everything from `site/js/data.js`, which is generated from the data files and not committed. See `site/README.md` for how a data file becomes a page.

- Build and check locally: `python scripts/build_site_data.py`, then `node scripts/check_site.js`, then open `site/index.html` in a browser.
- Every pull request runs both steps, so a data change that would break a page fails before it is merged.
- Every push to `main` rebuilds and republishes the site.
- A pull request that only changes files under `data/frontiers/`, `data/datasets/` or `scripts/import_*` is merged automatically once validation passes, and the site is republished (`.github/workflows/auto-merge.yml`). Anything else waits for a person.

## Automatic refresh

The **Refresh data** workflow (`.github/workflows/refresh.yml`) runs every day at 10:23 UTC. It runs each fetcher in `scripts/fetchers/`, and each fetcher reads one frontier's machine-readable source, then:

1. Validates the result. A fetcher that fails, or whose output doesn't validate, is reverted and listed in a "Data refresh failures" issue.
2. Puts the changes on a `refresh/<date>-<run>` branch and opens a pull request with a report of what changed.
3. Merges the pull request and rebuilds the site, unless something needs review. Review is needed when existing entries were removed, or when more than 10% of them changed at once. Those pull requests are left open with a comment.

To run it by hand, open the Actions tab, choose "Refresh data", then "Run workflow". You can limit it to some fetchers and choose a dry run. Set the repository variable `AUTO_MERGE` to `false` to turn automatic merging off.

To add a fetcher, copy `scripts/fetchers/erdos_problems.py`: define `FRONTIER` and a `fetch()` that returns one line per change and raises on anything unexpected. Test it locally with `python scripts/refresh.py --only <name>`.

Frontiers with no machine-readable source are checked by a scheduled Claude run, which opens pull requests for a person to review.
