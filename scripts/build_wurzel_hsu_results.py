#!/usr/bin/env python3
"""Build data/datasets/wurzel-hsu-lawson/results.csv from the Wurzel & Hsu data pickle.

Usage (needs pandas, which the rest of the repo does not):
  python -I scripts/build_wurzel_hsu_results.py PATH/TO/experimental_results_published_2025.pkl

The pickle comes from https://github.com/swurzel/lawson-criterion-paper (data/). It is loaded
with an unpickler that only allows the pandas, numpy and datetime classes a DataFrame needs,
so a tampered file cannot run code.

The triple product and Q_sci are re-implemented here from lawson-criterion-paper.py (the
authors' notebook), not imported from it:
  - MCF: n_i0 * T_i0 * tau_E*. Missing peak values are inferred as the notebook does: peak
    from volume average using the concept's peaking factor, ion from electron quantities,
    and tau_E* = tau_E when only tau_E is given.
  - ICF/MIF: p*tau = p_stag * tau_stag (Gbar converted to atm), or for 2007-2009 OMEGA shots
    without a reported pressure the Betti 2010 formula; then n<T>tau = p*tau * 6.325e20 / 2.
  - Q_sci: fusion energy / input energy where given, otherwise fusion power / heating power.
The triple product is rounded to two significant figures and Q_sci to two decimals, which is
how the paper's tables print them. The output was checked against every row of Tables I-IV of
arXiv:2505.03834v6.
"""
import io
import math
import pickle
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "datasets" / "wurzel-hsu-lawson" / "results.csv"

ALLOWED = {
    ("builtins", "slice"), ("datetime", "date"), ("numpy", "dtype"), ("numpy", "ndarray"),
    ("numpy._core.multiarray", "_reconstruct"), ("numpy._core.numeric", "_frombuffer"),
    ("pandas._libs.internals", "_unpickle_block"), ("pandas.core.frame", "DataFrame"),
    ("pandas.core.indexes.base", "_new_Index"), ("pandas.core.indexes.base", "Index"),
    ("pandas.core.internals.managers", "BlockManager"),
}


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) not in ALLOWED:
            raise pickle.UnpicklingError(f"refusing to load {module}.{name}")
        return super().find_class(module, name)


# The published-2025 pickle uses short concept names; the notebook maps them to these.
CONCEPT_NAMES = {"FRC": "Field Reversed Configuration", "RFP": "Reverse Field Pinch",
                 "Pinch": "Stabilized Pinch", "MTF": "Magnetized Target Fusion",
                 "MagLIF": "Magnetized Liner Inertial Fusion"}
# Peak / volume-average for (temperature, density). Profiles of the form (1 - x^2)^a give a + 1
# (lib/plasmaprofile.py); FRC, RFP and spheromak values are quoted in the notebook.
PEAKING = {"Tokamak": (2.0, 1.5), "Spherical Tokamak": (2.1, 1.7), "Stellarator": (3.0, 1.0),
           "Field Reversed Configuration": (1.0, 1.3), "Reverse Field Pinch": (1.2, 1.2),
           "Spheromak": (2.0, 1.5)}
MCF = {"Tokamak", "Spherical Tokamak"}
MCF_OTHER = {"Stellarator", "Reverse Field Pinch", "Stabilized Pinch", "Spheromak", "Mirror",
             "Z Pinch", "Field Reversed Configuration", "Magnetized Target Fusion"}
ICF_MIF = {"Laser Direct Drive", "Laser Indirect Drive", "Magnetized Liner Inertial Fusion"}
ATM_PER_GBAR = 986923169.31427
KEV_M3_S_PER_ATM_S = 6.325e20
PROJECTIONS = {"SPARC", "ITER"}  # design projections in the published table, not achieved shots


def num(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return math.nan
    text = str(value).strip()
    return float(text) if text else math.nan


def blank(x):
    return isinstance(x, float) and math.isnan(x)


def sig2(x):
    return "" if blank(x) else f"{float(f'{x:.1e}'):g}"


def sig3(x):
    return "" if blank(x) else f"{float(f'{x:.3g}'):g}"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    df = RestrictedUnpickler(io.BytesIO(Path(sys.argv[1]).read_bytes())).load()
    out = []
    for _, r in df.iterrows():
        concept = CONCEPT_NAMES.get(r["Concept Displayname"], r["Concept Displayname"])
        project = r["Project Displayname"]
        date = str(r["Date"]) if not pd.isnull(r["Date"]) else str(int(r["Year"]))
        lawson = bool(r["include_lawson_plots"])
        in_qsci = bool(r["include_Qsci_vs_date_plot"])
        projection = project in PROJECTIONS
        inferred = []
        table = []
        nttau = temp = math.nan
        temp_kind = definition = ""
        if lawson and (concept in MCF or concept in MCF_OTHER):
            table.append("I" if concept in MCF else "II")
            p_t, p_n = PEAKING.get(concept, (math.nan, math.nan))
            t_i = num(r["T_i_max"])
            if blank(t_i) and not blank(num(r["T_i_avg"])):
                t_i = num(r["T_i_avg"]) * p_t
                inferred.append("peak ion temperature inferred from volume average")
            elif blank(t_i) and not blank(num(r["T_e_max"])):
                t_i = num(r["T_e_max"])
                inferred.append("ion temperature inferred from electron temperature")
            elif blank(t_i) and not blank(num(r["T_e_avg"])):
                t_i = num(r["T_e_avg"]) * p_t
                inferred.append("ion temperature inferred from volume-averaged electron temperature")
            n_i = num(r["n_i_max"])
            if blank(n_i) and not blank(num(r["n_i_avg"])):
                n_i = num(r["n_i_avg"]) * p_n
                inferred.append("peak ion density inferred from volume average")
            elif blank(n_i) and not blank(num(r["n_e_max"])):
                n_i = num(r["n_e_max"])
                inferred.append("ion density inferred from electron density")
            elif blank(n_i) and not blank(num(r["n_e_avg"])):
                n_i = num(r["n_e_avg"]) * p_n
                inferred.append("ion density inferred from volume-averaged electron density")
            tau_star, tau = num(r["tau_E_star"]), num(r["tau_E"])
            if blank(tau_star):
                tau_star = tau
            elif not blank(tau) and tau != tau_star:
                inferred.append("tau_E* inferred from measured tau_E")
            nttau, temp = t_i * n_i * tau_star, t_i
            temp_kind, definition = "peak ion temperature T_i0", "n_i0 T_i0 tau_E*"
        elif lawson and concept in ICF_MIF:
            table.append("III")
            if not pd.isnull(r["p_stag"]) and not pd.isnull(r["tau_stag"]):
                ptau = num(r["p_stag"]) * ATM_PER_GBAR * num(r["tau_stag"])
            else:
                ptau = 8 * (num(r["rhoR_tot"]) * num(r["T_i_avg"])) ** 0.8 * num(r["YOC"]) ** 0.5
                inferred.append("p*tau inferred from areal density, temperature and yield-over-clean (Betti 2010)")
            nttau = 0.5 * ptau * KEV_M3_S_PER_ATM_S
            temp, temp_kind = num(r["T_i_avg"]), "burn-averaged ion temperature <T_i>_n"
            if blank(temp):
                temp, temp_kind = num(r["T_e_avg"]), "electron temperature (no ion temperature reported)"
            definition = "n <T_i>_n tau_stag"
        q_sci, basis = math.nan, ""
        if in_qsci:
            table.append("IV")
            e_f, e_in, p_f, p_in = (num(r[c]) for c in ("E_F", "E_ext", "P_F", "P_ext"))
            if not blank(e_f) and not blank(e_in):
                q_sci, basis = e_f / e_in, "energy (fusion yield / laser energy)"
            else:
                q_sci, basis = p_f / p_in, "power (fusion power / heating power)"
        if blank(q_sci):
            q_text = ""
        elif round(q_sci, 2) == 0:
            q_text = f"{float(f'{q_sci:.2g}'):g}"  # the table prints 0.00; keep two significant figures
        else:
            q_text = f"{q_sci:.2f}"
        if concept == "Magnetized Liner Inertial Fusion":
            fuel = "D-D"
        elif in_qsci:
            fuel = "D-T"
        else:
            fuel = ""
        out.append({
            "wh_id": int(r["id"]), "project": project, "concept": concept, "date": date,
            "shot": str(r["Shot"]), "paper_tables": " ".join(table), "is_projection": projection,
            "triple_product_kev_m3_s": sig2(nttau), "triple_product_definition": definition,
            "temperature_kev": sig3(temp), "temperature_kind": temp_kind,
            "q_sci": q_text, "q_sci_basis": basis,
            "q_sci_comment": r["Qsci_comment"] if isinstance(r["Qsci_comment"], str) and r["Qsci_comment"] != "nan" else "",
            "fuel_stated": fuel, "inferred": "; ".join(inferred),
            "new_or_changed_2025": bool(r["new_or_changed_2025_update"]),
            "references": " ".join(r["Bibtex Strings"]) if isinstance(r["Bibtex Strings"], (list, tuple)) else str(r["Bibtex Strings"]),
        })
    res = pd.DataFrame(out).sort_values(["date", "wh_id"], key=lambda s: s.astype(str))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, lineterminator="\n")
    print(f"Wrote {len(res)} rows to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
