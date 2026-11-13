# Epoch Capabilities Index scores

Epoch AI's Epoch Capabilities Index (ECI) for 255 language models, one row per model. It feeds the `ai-capabilities-index` frontier. See NOTICE.md for the licence and required credit.

| | |
| --- | --- |
| Publisher | Epoch AI |
| Source page | https://epoch.ai/eci |
| Original file | https://epoch.ai/data/eci_scores.csv |
| Method | https://epoch.ai/data/eci-documentation and https://github.com/epoch-research/eci-public |
| Retrieved | 2026-11-13 |
| eci_scores.csv SHA-256 | 2e84d024de3b0b838f4e33229e3082738fed6b3f98d4b199e25b6abe01faac19 |

## How eci_scores.csv was made

It is Epoch's file byte for byte, with no changes. Columns, as Epoch names them: `Model`, `Display name`, `eci`, `eci_ci_low`, `eci_ci_high`, `date` (the model's date as Epoch lists it), `Organization`, `Country (of organization)`, `Model accessibility`, `Accessibility group` (Closed weights, Open weights or Other), `model_versions`.

The 2026-11-09 copy was downloaded by the repository's GitHub Actions runner, because the cloud shell cannot reach epoch.ai, and its checksum was matched against the runner's before it was committed.

## Things to know

- Epoch fits all scores together from benchmark results across more than 50 benchmarks, and refits when new results arrive, so past models' scores can move between versions of this file. Two models carry fixed scores and no interval (Claude 3.5 Sonnet at 130 and GPT-5 at 150 in this copy), which appear to pin the scale; Epoch's documentation pages opened on 2026-11-09 did not state this, so it is an observation, not Epoch's statement.
- The interval columns are Epoch's; the documentation opened did not state their level.

## Updating

`scripts/fetchers/epoch_eci.py` downloads the file daily (through the refresh workflow), replaces it when it changed, updates the date and checksum above, and runs `python scripts/import_epoch_eci.py` to rebuild the frontier's records.
