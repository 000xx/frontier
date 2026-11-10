"""Refresh the polio frontier's OWID-sourced observations (WPV1 and cVDPV) from Our World in Data.

Both series come from OWID's CSV exports of WHO polio data, read for the World entity. The
cVDPV total for a year is the sum of the VDPV1, VDPV2 and VDPV3 columns, as the frontier
notes describe. Only observations whose source is OWID are changed. A year that OWID
publishes and the frontier does not yet have is added with the OWID source. Years already
held from WHO or GPEI are left alone.

GPEI's weekly counts have no machine-readable feed, so they are not fetched here.
"""
import csv
import io
import re

from . import common

FRONTIER = "data/frontiers/health/polio.yaml"
WPV1_URL = "https://ourworldindata.org/grapher/cases-of-paralytic-polio-from-wild-polioviruses.csv"
CVDPV_URL = "https://ourworldindata.org/grapher/cases-of-paralytic-polio-from-vaccine-derived-viruses-by-strain.csv"
WPV1_SOURCE = "owid-wpv1"
CVDPV_SOURCE = "owid-cvdpv"
ID_COLUMNS = ("Entity", "Code", "Year")


def _world_rows(raw, label):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    header = reader.fieldnames or []
    missing = [c for c in ID_COLUMNS if c not in header]
    if missing:
        raise common.SourceError(f"{label}: columns {missing} are missing; header was {header}")
    rows = [r for r in reader if r.get("Entity") == "World"]
    if not rows:
        raise common.SourceError(f"{label}: no World rows found")
    return header, rows


def _count(text, where):
    text = (text or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        raise common.SourceError(f"{where}: {text!r} is not a number")
    if number < 0 or number != int(number):
        raise common.SourceError(f"{where}: {text!r} is not a whole count")
    return int(number)


def _year_totals(rows, columns, label):
    """Sum the given value columns per year. A blank cell counts as zero; a year with no values is skipped."""
    totals = {}
    for row in rows:
        try:
            year = int(str(row["Year"]).strip())
        except ValueError:
            raise common.SourceError(f"{label}: unreadable year {row['Year']!r}")
        values = [_count(row.get(c), f"{label} {year} {c}") for c in columns]
        present = [v for v in values if v is not None]
        if not present:
            continue
        if year in totals:
            raise common.SourceError(f"{label}: year {year} appears twice")
        totals[str(year)] = sum(present)
    return totals


def _wpv1_counts(raw):
    header, rows = _world_rows(raw, "WPV1 export")
    value_columns = [c for c in header if c not in ID_COLUMNS]
    if len(value_columns) != 1:
        raise common.SourceError(f"WPV1 export: expected one value column, found {value_columns}")
    return _year_totals(rows, value_columns, "WPV1")


def _cvdpv_counts(raw):
    header, rows = _world_rows(raw, "cVDPV export")
    strains = {}
    for column in header:
        if column in ID_COLUMNS or "VDPV" not in column.upper():
            continue
        match = re.search(r"VDPV\s*([123])", column, re.IGNORECASE)
        if not match or match.group(1) in strains:
            raise common.SourceError(f"cVDPV export: unexpected or repeated column {column!r}")
        strains[match.group(1)] = column
    if sorted(strains) != ["1", "2", "3"]:
        raise common.SourceError(f"cVDPV export: expected VDPV1, VDPV2 and VDPV3 columns, found {sorted(strains)}")
    return _year_totals(rows, [strains[k] for k in ("1", "2", "3")], "cVDPV")


SERIES = [
    # (series id, label, CSV url, OWID source id, parser)
    ("wpv1", "WPV1", WPV1_URL, WPV1_SOURCE, _wpv1_counts),
    ("cvdpv", "cVDPV", CVDPV_URL, CVDPV_SOURCE, _cvdpv_counts),
]


def _replace_value(text, series, year, source, value):
    pattern = re.compile(
        rf"(- date: '{year}'\n  series: {series}\n  value: )\d+(\n  source: {re.escape(source)}\n)")
    new, count = pattern.subn(lambda m: f"{m.group(1)}{value}{m.group(2)}", text)
    if count != 1:
        raise common.SourceError(f"could not find the {series} {year} observation from {source} exactly once")
    return new


def _insert_observation(text, series, year, source, value):
    lines = text.split("\n")
    start = lines.index("observations:")
    end = next(i for i in range(start + 1, len(lines))
               if lines[i] and not lines[i].startswith((" ", "-")))
    blocks = [i for i in range(start + 1, end) if lines[i].startswith("- date: ")]
    mine = [i for i in blocks if lines[i + 1] == f"  series: {series}"]
    if not mine:
        raise common.SourceError(f"no {series} observations found in {FRONTIER}")

    def block_year(i):
        match = re.match(r"- date: '(\d{4})'$", lines[i])
        if not match:
            raise common.SourceError(f"unexpected observation layout at line {i + 1} of {FRONTIER}")
        return int(match.group(1))

    later = [i for i in mine if block_year(i) > int(year)]
    if later:
        at = later[0]
    else:
        at = next((i for i in blocks if i > mine[-1]), end)
    lines[at:at] = [f"- date: '{year}'", f"  series: {series}", f"  value: {value}", f"  source: {source}"]
    return "\n".join(lines)


def fetch():
    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    observations = common.load(FRONTIER).get("observations") or []
    messages = []
    for series, label, url, source, parse in SERIES:
        counts = parse(common.get(url))
        existing = {str(o["date"]): o for o in observations if o.get("series") == series}
        owid = {year: o for year, o in existing.items() if o.get("source") == source}
        gone = sorted(set(owid) - set(counts))
        if gone:
            raise common.SourceError(f"{label}: OWID no longer publishes {', '.join(gone)}")
        for year in sorted(owid):
            if owid[year]["value"] != counts[year]:
                text = _replace_value(text, series, year, source, counts[year])
                messages.append(f"{label} {year}: {owid[year]['value']} -> {counts[year]} (OWID)")
        for year in sorted(set(counts) - set(existing), key=int):
            text = _insert_observation(text, series, year, source, counts[year])
            messages.append(f"{label} {year} added: {counts[year]} (OWID)")

    if not messages:
        return []
    common.write_if_changed(FRONTIER, text)
    updated = common.load(FRONTIER).get("observations") or []
    if len(updated) != len(observations) + sum("added" in m for m in messages):
        raise common.SourceError("observation count after the edit does not match the expected change")
    return messages
