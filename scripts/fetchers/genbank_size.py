"""Refresh the GenBank size frontier from the release table on NCBI's GenBank statistics page.

The table has one row per flat-file release: release number, release month, bases and sequences for traditional
GenBank records. Each release is stored under its month (YYYY-MM) as two observations, one for bases and one for
sequences. New releases are added. The last three releases are rewritten when their figures change; older releases
are kept as they are, and any change to them is printed in the run log only, because the source can revise them.
"""
import html
import re

from . import common

FRONTIER = "data/frontiers/biology/genbank-size.yaml"
URL = "https://www.ncbi.nlm.nih.gov/genbank/statistics"
SOURCE_ID = "ncbi-genbank-statistics"
SERIES_ORDER = ("bases", "sequences")
REWRITE_WINDOW = 3
MIN_RELEASES = 200
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
TAGS = re.compile(r"<[^>]+>")
RELEASE = re.compile(r"^\d+(\.\d+)?$")
DATE = re.compile(r"^([A-Z][a-z]{2}) (\d{4})$")


def parse_table(raw):
    """Return {'YYYY-MM': (bases, sequences)} from the release rows. Raises SourceError if the format looks wrong."""
    text = raw.decode("utf-8", "replace")
    by_month = {}
    seen_releases = set()
    for row in ROW.findall(text):
        cells = [html.unescape(TAGS.sub("", c)).replace("\xa0", " ").strip() for c in CELL.findall(row)]
        if len(cells) < 4 or not RELEASE.match(cells[0]):
            continue
        m = DATE.match(cells[1])
        if not m or m.group(1) not in MONTHS:
            raise common.SourceError(f"unexpected date in release {cells[0]}: {cells[1]!r}")
        bases_text = cells[2].replace(",", "")
        seq_text = cells[3].replace(",", "")
        if not (bases_text.isdigit() and seq_text.isdigit()):
            raise common.SourceError(f"unexpected counts in release {cells[0]}: {cells[2]!r}, {cells[3]!r}")
        if cells[0] in seen_releases:
            raise common.SourceError(f"release {cells[0]} appears twice")
        seen_releases.add(cells[0])
        month = f"{m.group(2)}-{MONTHS.index(m.group(1)) + 1:02d}"
        if month in by_month:
            raise common.SourceError(f"two releases dated {month}")
        by_month[month] = (int(bases_text), int(seq_text))
    if len(by_month) < MIN_RELEASES:
        raise common.SourceError(f"only {len(by_month)} releases found; expected at least {MIN_RELEASES}")
    return by_month


def fetch():
    world = parse_table(common.get(URL))
    months = sorted(world)
    print(f"DIAG releases: {len(months)}, {months[0]} to {months[-1]}")
    for month in months:
        bases, seqs = world[month]
        print(f"DIAG value {month} bases {bases} sequences {seqs}")

    data = common.load(FRONTIER)
    observations = data.get("observations") or []
    if any(o.get("source") != SOURCE_ID for o in observations):
        raise common.SourceError("the frontier has observations from a source this fetcher does not own")
    old = {(str(o["date"]), o["series"]): int(o["value"]) for o in observations}

    recent = set(months[-REWRITE_WINDOW:])
    keep = {}
    changes = []
    for month in months:
        for series, value in zip(SERIES_ORDER, world[month]):
            key = (month, series)
            if key not in old:
                keep[key] = value
                changes.append(f"{month} {series}: {value} added")
            elif old[key] == value:
                keep[key] = value
            elif month in recent:
                keep[key] = value
                changes.append(f"{month} {series}: {old[key]} -> {value}")
            else:
                keep[key] = old[key]
                print(f"DIAG older release revised at source, not rewritten: {month} {series} "
                      f"file {old[key]} source {value}")
    for key in sorted(set(old) - set(keep)):
        keep[key] = old[key]
        print(f"DIAG not in source, kept: {key}")
    print(f"DIAG existing: {len(old)} observations; changes: {len(changes)}")
    if not changes:
        return []

    path = common.ROOT / FRONTIER
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition("\nobservations:\n")
    if not sep or sep in tail or any(line and not line.startswith("- {") for line in tail.splitlines()):
        raise common.SourceError("the observations block is not in the expected form")
    ordered = sorted(keep, key=lambda k: (k[0], SERIES_ORDER.index(k[1])))
    lines = [f"- {{date: '{m}', series: {s}, value: {keep[(m, s)]}, source: {SOURCE_ID}}}" for m, s in ordered]
    path.write_text(head + sep + "\n".join(lines) + "\n", encoding="utf-8")
    return changes
