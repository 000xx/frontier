"""Refresh the solar-cell-efficiency frontier from NLR's Best Research-Cell Efficiency data table.

Rebuilds data/datasets/nlr-cell-efficiency/records.csv from the published workbook the way
that dataset's README describes, then runs scripts/import_nlr_cell_efficiency.py. The CSV is
byte-identical to the stored copy when the workbook has not changed. NOTICE.md is kept.
"""
import csv
import datetime as dt
import decimal
import email.utils
import io
import re
import urllib.request

import openpyxl

from . import common

FRONTIER = "data/frontiers/energy/solar-cell-efficiency.yaml"
DATASET = "data/datasets/nlr-cell-efficiency"
URL = "https://www.nlr.gov/docs/libraries/pv/cell-efficiency-data-table.xlsx"

COLUMNS = ["record_id", "measurement_date", "material_class", "cell_type", "description",
           "groups", "efficiency_pct", "uncertainty_pct", "area_cm2", "area_type", "suns",
           "test_center"]
# Output column -> workbook header (compared case-insensitively, whitespace collapsed).
# Headers that are matched by prefix because NLR adds explanations in parentheses.
HEADERS = {
    "record_id": ("Record Identifier", "exact"),
    "measurement_date": ("Measurement Date", "exact"),
    "material_class": ("Eff. Chart Material Class", "exact"),
    "cell_type": ("Eff. Chart Cell Type", "exact"),
    "description": ("Detailed description", "exact"),
    "groups": ("Group(s)", "exact"),
    "uncertainty_pct": ("Uncertainty (%)", "exact"),
    "area_cm2": ("Area (cm2)", "exact"),
    "area_type": ("Type of Area", "prefix"),
    "suns": ("Suns", "prefix"),
    "test_center": ("Accredited Testing Center", "prefix"),
}
# Efficiency: first non-empty of these columns.
EFFICIENCY = [("Combined efficiency (%)", "exact"), ("Revised/New", "prefix"), ("Efficiency", "prefix")]
EXCEL_EPOCH = dt.date(1899, 12, 30)


def _norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _find(headers, name, how):
    want = _norm(name)
    hits = [i for i, h in enumerate(headers)
            if (h == want if how == "exact" else h.startswith(want))]
    if how == "prefix" and len(hits) > 1:
        exact = [i for i in hits if headers[i] == want]
        hits = exact or hits
    if len(hits) != 1:
        raise common.SourceError(f"expected one column '{name}' in the workbook, found {len(hits)}; "
                                 f"headers: {headers}")
    return hits[0]


def js_number(x):
    """Format a number as JavaScript's String(Number(x.toPrecision(6)))."""
    if isinstance(x, bool) or x != x or x in (float("inf"), float("-inf")):
        raise common.SourceError(f"unexpected numeric value {x!r}")
    if x == 0:
        return "0"
    d = decimal.Decimal(x)  # exact binary value, as toPrecision uses
    exp = d.adjusted()
    quantum = decimal.Decimal(1).scaleb(exp - 5)
    # toPrecision picks the larger n on a tie: half-up for positives, half-down in magnitude
    # for negatives.
    mode = decimal.ROUND_HALF_UP if d > 0 else decimal.ROUND_HALF_DOWN
    rounded = d.quantize(quantum, rounding=mode, context=decimal.Context(prec=50))
    value = float(rounded)
    # Number.prototype.toString: shortest round-trip digits, exponent outside [1e-7, 1e21).
    sign = "-" if value < 0 else ""
    digits, exp10 = _shortest(abs(value))
    k = len(digits)
    n = exp10 + k  # position of the decimal point
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        mant = digits[0] + ("." + digits[1:] if k > 1 else "")
        body = f"{mant}e{'+' if e >= 0 else '-'}{abs(e)}"
    return sign + body


def _shortest(value):
    """Shortest round-trip decimal digits of a positive float, as (digits, exponent)."""
    s = repr(value)
    mant, _, e = s.partition("e")
    exp10 = int(e) if e else 0
    if "." in mant:
        whole, frac = mant.split(".")
    else:
        whole, frac = mant, ""
    if frac == "0":
        frac = ""
    digits = (whole + frac).lstrip("0")
    exp10 -= len(frac)
    stripped = digits.rstrip("0")
    exp10 += len(digits) - len(stripped)
    return stripped, exp10


def _text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        raise common.SourceError(f"unexpected boolean cell {value!r}")
    if isinstance(value, (int, float)):
        return js_number(value)
    if isinstance(value, (dt.datetime, dt.date)):
        raise common.SourceError(f"unexpected date cell {value!r} in a text or number column")
    return str(value).strip()


def _date(value, rid):
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return (EXCEL_EPOCH + dt.timedelta(days=int(value))).isoformat()
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return value.strip()
    raise common.SourceError(f"record {rid}: cannot read measurement date {value!r}")


def build_csv(raw):
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise common.SourceError(f"could not open the workbook: {exc}") from exc
    if len(wb.worksheets) != 1:
        raise common.SourceError(f"expected one sheet, found {wb.sheetnames}")
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    header_at = next((i for i, r in enumerate(rows[:20])
                      if any(_norm(c) == "record identifier" for c in r)), None)
    if header_at is None:
        raise common.SourceError("no 'Record Identifier' header row in the first 20 rows")
    headers = [_norm(c) for c in rows[header_at]]
    print("DIAG header row", header_at, headers)  # DIAG
    cols = {key: _find(headers, name, how) for key, (name, how) in HEADERS.items()}
    eff_cols = [_find(headers, name, how) for name, how in EFFICIENCY]

    out_rows = []
    for r in rows[header_at + 1:]:
        r = list(r) + [None] * (len(headers) - len(r))
        if all(c is None or (isinstance(c, str) and not c.strip()) for c in r):
            continue
        row = {key: _text(r[i]) for key, i in cols.items() if key != "measurement_date"}
        if not row["record_id"]:
            # Not a numbered record; the dataset has always left these out.
            print("DIAG skipped id-less row", r[:12])  # DIAG
            continue
        row = {"record_id": row["record_id"], "measurement_date": None, **row}
        row["measurement_date"] = _date(r[cols["measurement_date"]], row["record_id"])
        eff = next((_text(r[i]) for i in eff_cols if _text(r[i]) != ""), "")
        try:
            float(eff)
        except ValueError:
            raise common.SourceError(f"record {row['record_id']}: cannot read efficiency {eff!r}") from None
        row["efficiency_pct"] = eff
        out_rows.append(row)

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(out_rows)
    return out.getvalue(), out_rows


def _last_modified():
    """The workbook's Last-Modified date as YYYY-MM-DD, or None if the server gives none."""
    req = urllib.request.Request(URL, method="HEAD", headers={"User-Agent": common.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            value = resp.headers.get("Last-Modified")
        return email.utils.parsedate_to_datetime(value).date().isoformat() if value else None
    except Exception:  # noqa: BLE001  (optional metadata only)
        return None


def _records(path):
    with open(common.ROOT / path, encoding="utf-8", newline="") as f:
        return {r["record_id"]: r for r in csv.DictReader(f)}


def fetch():
    raw = common.get(URL)
    csv_text, rows = build_csv(raw)
    csv_path = f"{DATASET}/records.csv"
    old = _records(csv_path)
    if len(rows) < 0.9 * len(old):
        raise common.SourceError(f"workbook has {len(rows)} records, down from {len(old)}")
    ids = [r["record_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise common.SourceError("duplicate record identifiers in the workbook")

    # DIAG start
    print(f"DIAG rows={len(rows)} old={len(old)} sha={common.sha256(csv_text.encode())}")
    print("DIAG last rows:", [(r['record_id'], r['measurement_date'], r['efficiency_pct']) for r in rows[-5:]])
    n = 0
    for r in rows:
        prev = old.get(r["record_id"])
        if prev is None:
            print("DIAG new", r)
        elif prev != r:
            n += 1
            if n <= 40:
                print("DIAG diff", r["record_id"], {k: (prev[k], r[k]) for k in COLUMNS if prev[k] != r[k]})
    print("DIAG changed", n, "missing", sorted(old.keys() - set(ids))[:20])
    # DIAG end
    if not common.write_if_changed(csv_path, csv_text):
        return []

    readme = f"{DATASET}/README.md"
    common.set_readme_row(readme, "Retrieved", common.today())
    modified = _last_modified()
    if modified:
        common.set_readme_row(readme, "Original file last modified", f"{modified} (server header)")
    common.set_readme_row(readme, "records.csv SHA-256", common.sha256(csv_text.encode("utf-8")))
    common.run_script("scripts/import_nlr_cell_efficiency.py")

    changes = []
    for r in rows:
        prev = old.get(r["record_id"])
        label = f"NLR record {r['record_id']} ({r['cell_type']}, {r['groups'] or 'group not listed'})"
        if prev is None:
            changes.append(f"{label} added: {r['efficiency_pct']}% on {r['measurement_date']}")
        elif prev != r:
            diffs = [f"{k} {prev[k]!r} -> {r[k]!r}" for k in COLUMNS if prev[k] != r[k]]
            changes.append(f"{label} changed: " + "; ".join(diffs))
    for rid in old.keys() - set(ids):
        changes.append(f"NLR record {rid} no longer in the workbook")
    if [i for i in ids if i in old] != [i for i in old if i in set(ids)]:
        changes.append("Workbook rows were reordered")
    return changes or ["records.csv updated"]
