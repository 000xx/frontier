# NLR research-cell efficiency records

The record table behind NLR's Best Research-Cell Efficiency Chart: 562 certified record cells from 1976 onward. It feeds the `solar-cell-efficiency` frontier. See NOTICE.md for the terms of use and required credit.

| | |
| --- | --- |
| Publisher | National Laboratory of the Rockies (formerly NREL) |
| Source page | https://www.nlr.gov/pv/cell-efficiency |
| Original file | https://www.nlr.gov/docs/libraries/pv/cell-efficiency-data-table.xlsx |
| Data guide | https://www.nlr.gov/docs/libraries/pv/nrel-record-cell-efficiency-data-table-guide.pdf |
| Original file last modified | 2026-08-14 (server header) |
| Retrieved | 2026-11-09 |
| records.csv SHA-256 | 0d0d57c37f322e9b8923dfb44e294f8d57148e7fa8e60b6ee14c335e60700257 |

## How records.csv was made

From the single sheet of the original workbook, one row per record, keeping these columns:

| Column here | Original column |
| --- | --- |
| record_id | Record Identifier |
| measurement_date | Measurement Date, converted from an Excel serial date to YYYY-MM-DD |
| material_class | Eff. Chart Material Class |
| cell_type | Eff. Chart Cell Type |
| description | Detailed description |
| groups | Group(s) |
| efficiency_pct | Combined efficiency (%), the value NLR charts |
| uncertainty_pct | Uncertainty (%) |
| area_cm2 | Area (cm2) |
| area_type | Type of Area (da = designated illumination area, ap = aperture, t = total) |
| suns | Suns (concentration; 1 = no concentration) |
| test_center | Accredited Testing Centers |

Numbers were rounded to six significant figures to remove floating-point noise. Text is unchanged, including NLR's own spellings. Voltage, current density and fill factor were left out for now; they can be added from the original file.

## Updating

Download the original file again, regenerate records.csv the same way, record the new date and checksum above, then run `python scripts/import_nlr_cell_efficiency.py` to refresh the frontier file.
