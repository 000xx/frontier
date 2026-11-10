# WHO global malaria estimates

WHO's modelled estimates of malaria cases and deaths worldwide, one row per year and measure, 2000 to 2024, with the lower and upper bounds WHO gives. It feeds the `observations` of the `malaria` frontier. See NOTICE.md for the terms of use and required credit.

| | |
| --- | --- |
| Publisher | World Health Organization (WHO), Global Malaria Programme |
| Report the estimates belong to | World malaria report 2025, published 4 December 2025: https://www.who.int/teams/global-malaria-programme/reports/world-malaria-report-2025 |
| Where the numbers were read | WHO Global Health Observatory (GHO) OData API, indicators `MALARIA_EST_CASES` and `MALARIA_EST_DEATHS`, filtered to the global row |
| Cases URL | https://ghoapi.azureedge.net/api/MALARIA_EST_CASES?$filter=SpatialDim eq 'GLOBAL' |
| Deaths URL | https://ghoapi.azureedge.net/api/MALARIA_EST_DEATHS?$filter=SpatialDim eq 'GLOBAL' |
| Indicator pages | https://www.who.int/data/gho/data/indicators/indicator-details/GHO/estimated-number-of-malaria-cases |
| GHO records last updated | 2025-12-19 (the `Date` field on every record) |
| Retrieved | 2026-11-09 |
| estimates.csv SHA-256 | 66b8242b5284952d7440d3ca11e96a0ce741fe690cd1bb3a239ce0896339db91 |

## Why the GHO and not the report annex

The report's own table of estimated cases and deaths by country and year is Annex 4H, an Excel file (https://www.who.int/publications/m/item/annexes-world-malaria-report-2025). It could not be opened from the environment this was built in. The GHO records were updated on 19 December 2025, two weeks after the report came out, and they match every global figure the report's executive summary prints: 282 million cases in 2024, 273 million in 2023 and 230 million in 2015; 610 000 deaths in 2024 and 578 000 in 2015. When Annex 4H can be opened, its global rows should be compared with this file.

## How estimates.csv was made

Each GHO record for the global aggregate became one row. Each query was read twice and the two readings agreed.

| Column here | GHO field |
| --- | --- |
| year | TimeDim |
| measure | `cases` for MALARIA_EST_CASES, `deaths` for MALARIA_EST_DEATHS |
| value | NumericValue (WHO's point estimate), trailing zero decimals dropped |
| low | Low (lower bound of WHO's uncertainty range) |
| high | High (upper bound) |

Nothing else was changed. WHO's report rounds these numbers (282 million, 610 000); the site may round for display but should keep this file unrounded.

## What the numbers are

These are WHO estimates, not reported counts. The GHO indicator page says that, for countries and areas outside Africa, reported confirmed cases are adjusted for treatment seeking, under-reporting and lack of case confirmation, and points to the method described in the World malaria report 2022 (pages 208-212). Read that method before describing it on the site. A new report may revise earlier years, so replace the whole file with each new report rather than appending a year.

## Updating

When a new World malaria report is published (usually in December), check that the GHO `Date` field has moved, read both indicators again, rebuild estimates.csv, record the new dates and checksum above, and update the `observations` in data/frontiers/health/malaria.yaml to match.
