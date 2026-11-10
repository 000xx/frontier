# Instructions for update runs

This repository is the data backend for a site tracking scientific and technological frontiers. Read README.md for the layout and data format.

## Rules

- Never push to `main`. Put every change on a branch named `update/<frontier-id>-<YYYY-MM-DD>` and open a pull request.
- Every new record and event needs a source you actually opened. Do not add values from memory.
- Use `confirmed` only when an independent lab, registry or replication confirms the result. A company announcement is `claimed`; a refereed paper is `peer_reviewed`.
- If a source contradicts an existing record, do not delete it. Add a note, or set it to `retracted` if the claim was withdrawn, and explain why in the pull request.
- Write `why_it_matters` lines in your own words, in one sentence. Do not copy text from articles.
- Run `python scripts/validate.py` before opening the pull request; it must pass.

## An update run

1. Find frontiers that are due: `python scripts/validate.py` lists overdue ones.
2. For each, check the primary source first, then the others.
3. Add new records and up to five events per month that genuinely matter. Failures and retractions count.
4. Set `update.last_checked` to today, even if nothing changed.
5. Open one pull request per frontier, listing what changed and the source for each change.
