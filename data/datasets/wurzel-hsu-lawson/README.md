# Wurzel & Hsu Lawson-criterion results

Experimental fusion results compiled by Samuel E. Wurzel and Scott C. Hsu for their papers on progress against the Lawson criterion: 124 rows covering magnetic, magneto-inertial and inertial confinement experiments from 1957 to 2025. The data feeds the `fusion-performance` frontier. See NOTICE.md for the licence and required credit.

| | |
| --- | --- |
| Authors | Samuel E. Wurzel, Scott C. Hsu |
| Repository | https://github.com/swurzel/lawson-criterion-paper |
| Original file | https://raw.githubusercontent.com/swurzel/lawson-criterion-paper/main/data/experimental_results_published_2025.pkl |
| What it is | The data set frozen as published in Phys. Plasmas 32, 112106 (2025), https://doi.org/10.1063/5.0297357 (arXiv:2505.03834v6) |
| Original file SHA-256 | 9e9440fa894cffab96b0f15ebad5f6f36d67d2a2d16c7d5dd798072ead58627c (34,849 bytes; ETag f62df212b8eca6fcb230e600226c8231fd1302a0cdc36394c2a00e16ba4727e3) |
| Retrieved | 2026-11-09 (US time; the server's date header reads 2026-11-10 03:10 GMT) |
| results.csv SHA-256 | b0d1760f5585c67e7e20ac008450cb08e2efd80aac3ff192677382542f8dc6fc |

## How results.csv was made

The repository stores its data only as pandas pickles; the CSV tables its notebook writes are not committed. `scripts/build_wurzel_hsu_results.py` loads the pickle with a restricted unpickler that only accepts the pandas, numpy and datetime classes a DataFrame needs. Before loading, the pickle was disassembled with `pickletools` to confirm that it references no other classes. The script then recomputes the derived quantities with an independent re-implementation of the authors' notebook (`lawson-criterion-paper.py`). It does not run their code.

| Column | Meaning |
| --- | --- |
| wh_id | The row id in the authors' data set |
| project, concept, shot | As in the source. The short concept names in the published pickle (FRC, RFP, Pinch, MTF, MagLIF) are expanded the way the notebook expands them. |
| date | Full date where the source gives one, otherwise the year |
| paper_tables | Which of the paper's Tables I-IV list the row |
| is_projection | True for the SPARC and ITER design projections, which are not achieved results |
| triple_product_kev_m3_s | Magnetic confinement: n_i0·T_i0·τ_E*. Inertial and higher-density magneto-inertial: n·⟨T_i⟩_n·τ_stag from p_stag·τ_stag, or the Betti 2010 formula for 2007-2009 OMEGA shots. Rounded to two significant figures, as the tables print it. |
| triple_product_definition | Which of the two definitions applies |
| temperature_kev, temperature_kind | Peak ion temperature (magnetic) or burn-averaged ion temperature (inertial); FIREX reports only an electron temperature. Three significant figures. |
| q_sci, q_sci_basis, q_sci_comment | Scientific gain from Table IV: fusion energy over laser energy, or fusion power over heating power, to two decimals. TFTR 68522 is printed as 0.00 in the table; it is kept here at two significant figures (0.0021). |
| fuel_stated | D-T for rows in the paper's Q_sci plot, which its caption describes as D-T experiments; D-D for MagLIF on Z, which the paper says uses pure deuterium; blank where the source does not say |
| inferred | The source's footnote flags: peak values inferred from averages, ion values from electron values, or τ_E* from τ_E |
| new_or_changed_2025 | The source's flag for rows added or changed since the 2022 paper |
| references | The authors' BibTeX keys for the original measurements |

Where values were missing, the inference rules (peaking factors, ion-from-electron substitution, τ_E* = τ_E) follow the notebook. The peaking factors are tokamak 2.0/1.5, spherical tokamak 2.1/1.7, stellarator 3.0/1.0, FRC 1.0/1.3, RFP 1.2/1.2 and spheromak 2.0/1.5 (temperature/density).

**Check against the paper:** every one of the 107 achieved triple products, and every Q_sci value, matches Tables I-IV of arXiv:2505.03834v6 at the printed precision.

## What was left out

- The raw measured inputs (densities, confinement times, pressures, energies). They are in the original pickle and can be added later.
- The repository's ongoing, unpublished data set (`data/experimental_results.pkl`, SHA-256 e2c20c878e76362344e1d588b442a7303e81daa18db460b3313f7af01640efdf). It adds 7 rows: FT 1981, HL-3 2025-05-16, W7-X 2024-12-04, and Z Facility shots z3576, z3236 (a second entry), z3926 and z3952. These were left out because they are not yet in a refereed version.

## Updating

When the authors publish a new frozen data set, download it, run `python -I scripts/build_wurzel_hsu_results.py <pickle>`, and check the output against the new paper's tables. Then record the new checksums above and run `python scripts/import_wurzel_hsu_lawson.py`.
