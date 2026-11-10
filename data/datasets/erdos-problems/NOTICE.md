# Notice for this dataset

`problems.csv` is derived from, and `statistics_history.csv` is copied from, the Erdős problems database at https://github.com/teorth/erdosproblems. It is the work of the Erdős problems database contributors and is maintained by Thomas Bloom and Terence Tao.

Licence: Apache License, Version 2.0. A full copy is in `LICENSE` in this folder, as section 4(a) of the licence requires. The upstream repository has no NOTICE file.

Changes (section 4(b)): `problems.csv` is a reformatting of `data/problems.yaml` into one CSV row per problem, with some fields left out; see README.md. `statistics_history.csv` is unchanged.

Credit: the upstream CITATIONS.cff asks that authorship be given as "Erdős problems database contributors". Pages and charts drawn from this data should carry the line "Data: Erdős problems database (github.com/teorth/erdosproblems), Erdős problems database contributors, maintained by Thomas Bloom and Terence Tao. Problems from erdosproblems.com."

Not covered by this licence:

- erdosproblems.com, run by Thomas Bloom. It states no licence or terms of use that we could find, so no text from it is copied here. Frontier items only link to its problem pages.
- The "AI contributions to Erdős problems" wiki of the same GitHub repository. GitHub wikis are separate from the repository and the licence file does not clearly cover them. Only per-problem facts (wiki section, outcome rating, date) are used in the frontier file, with a link to the wiki; none of its text is stored.

Presentation request: on 2026-10-06 erdosproblems.com stopped displaying problem statuses and the count or share of problems solved, and the database moved its tallies off its front page in step, so that the problems are read as open questions rather than a scoreboard (see https://github.com/teorth/erdosproblems/blob/main/STATISTICS.md). This is not a licence condition, but anything on the site that headlines a solved count should be checked against it before going live.
