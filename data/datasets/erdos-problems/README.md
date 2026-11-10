# Erdős problems database

The community database of the problems on erdosproblems.com: 1221 problems, each with its status, Lean formalisation state, prize and tags, plus the database's own history of counts. It feeds the `erdos-problems` frontier. See NOTICE.md for the licence and required credit.

| | |
| --- | --- |
| Publisher | Erdős problems database contributors; maintained by Thomas Bloom and Terence Tao |
| Repository | https://github.com/teorth/erdosproblems |
| Original files | https://raw.githubusercontent.com/teorth/erdosproblems/main/data/problems.yaml and https://raw.githubusercontent.com/teorth/erdosproblems/main/data/statistics_history.csv |
| Upstream state | `main` as of 2026-11-09; last history row is commit 026e2e5 (2026-11-09 22:07:53 UTC) |
| Retrieved | 2026-11-09 |
| Original problems.yaml SHA-256 | e336ce43a06a1dbbf01398565f85d9bf40085e52882fa643e3d4f092eaf74a49 |
| problems.csv SHA-256 | d86b1170a60f4fb98f267066fa78b1f3349d95cf4f4a0c2164bb9351d0b719f0 |
| statistics_history.csv SHA-256 | 8681cd4fe1bb7c1f0afd8c9f9f0e9eff136abf5a20dc2b1ba81558a3677b2ae4 |
| Licence | Apache License 2.0 (copy in LICENSE) |

The database is crowdsourced and unofficial. Its maintainers say erdosproblems.com is the more reliable source when the two differ.

## How the files were made

`statistics_history.csv` is an unchanged copy. Each row is a commit to the upstream database with its counts at that point. The first rows of 2025-08-31 were written while the problems were still being imported, so their totals jump from 2 to 992.

`problems.csv` was made from `problems.yaml`, one row per problem, sorted by number:

| Column here | Original field |
| --- | --- |
| number | number |
| prize | prize |
| status | status.state (derived upstream; informal status plus " (Lean)" when a Lean solution exists) |
| status_last_update | status.last_update |
| informal_status | informal_status.state |
| informal_last_update | informal_status.last_update |
| formal_status | formal_status.state |
| formal_last_update | formal_status.last_update |
| statement_formalized | formalized.state (statement formalised in Google DeepMind's Formal Conjectures repository) |
| tags | tags, joined with ";" |
| comments | comments |

OEIS links and formalisation URLs were left out; they can be added from the original file. Text is unchanged.

The `last_update` dates record when the database entry last changed, not when a problem was solved.

## Updating

Download both original files again, regenerate problems.csv the same way, and record the new date and checksums above. Then run `python scripts/import_erdos_problems.py` to refresh the frontier file. Add `--ai-wiki <path>` to re-read AI involvement from a downloaded copy of the AI-contributions wiki. That wiki has been frozen since 2026-06-30, and its text is not stored here.
