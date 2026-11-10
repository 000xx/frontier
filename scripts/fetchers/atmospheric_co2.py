"""Refresh the atmospheric CO2 frontier from NOAA's Mauna Loa annual-mean file.

The file has comment lines starting with '#', then one line per year: year, annual mean (ppm), uncertainty.
Years with no valid mean (NOAA writes -9.99) are skipped as not yet published. Existing years must keep their
values; new years are added. Values are written with two decimals, as NOAA publishes them.
"""
import re

from . import common

FRONTIER = "data/frontiers/earth/atmospheric-co2.yaml"
URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt"
SOURCE_ID = "noaa-mlo-annual"
SERIES = "mauna-loa-annual"
FIRST_YEAR = 1959
MIN_YEARS = 60
MISSING = -9.99


def read_annual(raw):
    """Return {year: mean_ppm}. Raises SourceError if the format looks wrong."""
    text = raw.decode("utf-8", errors="replace")
    years = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3:
            raise common.SourceError(f"unexpected data line: {line!r}")
        if not re.fullmatch(r"\d{4}", parts[0]):
            raise common.SourceError(f"bad year in data line: {line!r}")
        try:
            mean = float(parts[1])
        except ValueError as exc:
            raise common.SourceError(f"mean is not a number: {line!r}") from exc
        year = int(parts[0])
        if year in years:
            raise common.SourceError(f"year {year} appears more than once")
        if mean == MISSING:
            continue
        if not 200 < mean < 1000:
            raise common.SourceError(f"mean for {year} is outside a plausible range: {mean}")
        years[year] = round(mean, 2)

    if min(years) != FIRST_YEAR:
        raise common.SourceError(f"first year is {min(years)}, expected {FIRST_YEAR}")
    if len(years) < MIN_YEARS:
        raise common.SourceError(f"only {len(years)} years found; expected at least {MIN_YEARS}")
    expected = list(range(FIRST_YEAR, max(years) + 1))
    gaps = [y for y in expected if y not in years]
    if gaps:
        raise common.SourceError(f"years missing from the middle of the series: {gaps[:5]}")
    return years


def render_observations(years):
    return [f"- {{date: '{year}', series: {SERIES}, value: {years[year]:.2f}, source: {SOURCE_ID}}}"
            for year in sorted(years)]


def fetch():
    raw = common.get(URL)
    years = read_annual(raw)
    ordered = sorted(years)
    print(f"DIAG NOAA years: {len(ordered)}, {ordered[0]} to {ordered[-1]}; "
          f"latest: {ordered[-1]} {years[ordered[-1]]:.2f} ppm")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {int(o["date"]): round(float(o["value"]), 2) for o in observations}

    removed = sorted(set(old) - set(years))
    if removed:
        raise common.SourceError(f"source no longer has {len(removed)} existing years, e.g. {removed[:3]}")

    changed = [y for y in sorted(old) if old[y] != years[y]]
    for y in changed:
        print(f"DIAG mismatch: {y} frontier {old[y]:.2f} source {years[y]:.2f}")
    if changed:
        raise common.SourceError(f"{len(changed)} existing values differ from NOAA; not overwriting them")

    added = [y for y in ordered if y not in old]
    for y in added:
        print(f"DIAG added: {y} {years[y]:.2f}")
    if not added:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    path.write_text(head + sep + "\n".join(render_observations(years)) + "\n", encoding="utf-8")
    return [f"{y}: annual mean {years[y]:.2f} ppm added" for y in added]
