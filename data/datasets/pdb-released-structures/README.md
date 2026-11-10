# PDB released structures per year

The yearly count of structures released to the Protein Data Bank, 1976 to 2024, with the running total. It feeds the `observations` of the `protein-structures` frontier. See NOTICE.md for the terms and the credit line.

| | |
| --- | --- |
| Publisher | RCSB Protein Data Bank (RCSB PDB), a member of the wwPDB |
| Source page | PDB Statistics: Overall Growth of Released Structures Per Year, https://bioinformatics.rcsb.org/stats/growth/growth-released-structures |
| Page as read | The table was read from the page at the URL above. The same page on www.rcsb.org did not return the table when read. |
| Coverage | Years 1976 to 2024. No row for 2025 was available when this was built. |
| Retrieved | 2026-11-09 |
| released-per-year.csv SHA-256 | 6b2a55777d914117a2b636ca28a3c3320bddbc3e26af7f33954891583f1e6e8a |

## How released-per-year.csv was made

The table on the page has three columns: the year, the number of structures released that year, and the total available by the end of that year. The page's own labels for these are "Structures Released Annually" and "Total Number of Entries Available". One row per year was kept, with the columns renamed `year`, `released_in_year` and `cumulative_total`. Commas in the thousands were removed. No values were changed.

Check: for every year, the running sum of `released_in_year` equals `cumulative_total`. All 49 rows agree. The 2024 total, 229,380, is 214,059 plus 15,321.

## Updating

RCSB publishes a new year's row on this page. When it appears, append the row, rerun the check above, and regenerate the `observations` in `data/frontiers/biology/protein-structures.yaml` from this file.
