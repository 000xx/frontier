# Instructions for update runs

This repository is the data backend for a site tracking scientific and technological frontiers. Read README.md for the layout, `schema/frontier.schema.json` for the format, and the existing frontiers under `data/frontiers/` as examples.

## How changes land

The owner wants updates to move with as few checkpoints as possible:

- Put every change on its own branch, named `update/<frontier-id>-<YYYY-MM-DD>`, and open a pull request once `python scripts/validate.py` passes.
- Once validation passes, merge your own pull request through the GitHub API (`gh api -X PUT repos/000xx/frontier/pulls/<n>/merge -f merge_method=merge`). The owner approved this on 2026-11-09. Never push to `main` directly, and never force-push.
- Do the whole job without stopping to ask. Raise a problem in the pull request description, and in your report back, when it needs the owner's judgment. Examples: a source's terms that restrict use, a maintainer's stated wishes, data you could not verify, or a number that looks wrong.

## Rules for data

- Every value must come from a source you actually opened. Never add values from memory or fill gaps with estimates.
- Use `confirmed` only when an independent lab, registry or replication confirms the result. A company announcement is `claimed`; a refereed paper is `peer_reviewed`.
- If a source contradicts an existing record, do not delete it. Add a note, or set it to `retracted` if the claim was withdrawn.
- Write `why_it_matters` lines and explainers in your own words. Do not copy text from articles, papers or reports.
- Check each source's license or terms before copying a dataset. A copied dataset goes in `data/datasets/<id>/` with a README.md (source, retrieval date, checksum, transformation) and a NOTICE.md (license, required credit line), following `data/datasets/nlr-cell-efficiency/`. If the terms don't allow copying, record facts with citations only.
- Respect what a source's maintainers have asked for, even when the license allows more. See `data/frontiers/mathematics/erdos-problems.yaml` for an example.
- Do not edit `schema/`, `scripts/validate.py`, `data/domains.yaml`, `data/chart-shapes.yaml`, `site/` or the root README in a frontier update. If the schema cannot express something, put it in a note and report it.

## Adding a new frontier

1. Create `data/frontiers/<domain>/<id>.yaml`. Domain and subfield must exist in `data/domains.yaml`; chart shapes must exist in `data/chart-shapes.yaml`.
2. Use `records` for best-ever results, `observations` for regular time series (costs, counts, shares), `items` for fixed lists, and `stages` plus `candidates` for things moving through stages.
3. Set `status: live` when the core data is complete and sourced, and `draft` otherwise.
4. Set `update.last_checked` to today and pick a sensible `update.cadence`.
5. Leave `reading` empty unless every link is real and you opened it.

## Environment notes

- The cloud shell can reach raw.githubusercontent.com and package registries, but most other sites are blocked. Use WebFetch and WebSearch for web pages.
- If a push or fetch gets HTTP 429, wait 10 seconds and retry, up to three times.
- Do not commit `__pycache__` or other generated files.
- Commit messages and pull request bodies end with the attribution lines given in the session.

## A routine update run

1. Find frontiers that are due: `python scripts/validate.py` lists overdue ones.
2. For each, check the primary source first, then the others.
3. Add new records, observations and up to five events per month that genuinely matter. Failures and retractions count.
4. Set `update.last_checked` to today, even if nothing changed.
5. One pull request per frontier, listing each change with its source; merge it once validation passes.
