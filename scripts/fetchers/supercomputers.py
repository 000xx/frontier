"""Refresh the TOP500 number-one frontier from the list pages at top500.org.

Each June and November edition is at https://www.top500.org/lists/top500/YYYY/MM/. The fetcher
walks forward from the newest recorded edition. A missing page means that list is not out yet.
A page that exists is parsed for its rank-1 row. A record is added only when the number-one system
changes or its Rmax improves, the same rule the existing records follow.
"""
import html as htmllib
import re
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

from . import common

FRONTIER = "data/frontiers/computing/supercomputers.yaml"
SOURCE_ID = "top500-lists"
PAGE = "https://www.top500.org/lists/top500/{edition}/"
UNIT_DIVISOR = {"GFlop/s": Decimal(1000000), "TFlop/s": Decimal(1000), "PFlop/s": Decimal(1)}


def _get(url):
    """Return (status, body). A 404 is returned, not raised; other failures raise SourceError."""
    req = urllib.request.Request(url, headers={"User-Agent": common.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return 404, ""
        raise common.SourceError(f"could not download {url}: HTTP {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        raise common.SourceError(f"could not download {url}: {exc}") from exc


def _text(fragment):
    plain = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", htmllib.unescape(plain)).strip()


def _next_edition(edition):
    year, month = (int(x) for x in edition.split("/"))
    return f"{year}/11" if month == 6 else f"{year + 1}/06"


def _edition_of(date):
    return f"{date[:4]}/{date[5:7]}"


def parse_number_one(page):
    """Return (name, site, published_value, unit) for the rank-1 row of a list page."""
    headers = [_text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", page, re.S)]
    rmax_cols = [i for i, h in enumerate(headers) if re.match(r"Rmax", h)]
    if len(rmax_cols) != 1:
        raise common.SourceError(f"expected one Rmax column, found headers {headers}")
    unit_match = re.search(r"(GFlop/s|TFlop/s|PFlop/s)", headers[rmax_cols[0]])
    if not unit_match:
        raise common.SourceError(f"Rmax header has no known unit: {headers[rmax_cols[0]]!r}")
    unit = unit_match.group(1)

    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if cells and _text(cells[0]) == "1":
            break
    else:
        raise common.SourceError("no rank-1 row on the list page")

    if len(cells) < len(headers) or len(headers) == 0:
        raise common.SourceError(f"rank-1 row has {len(cells)} cells, header has {len(headers)}")
    name_cell = cells[1]
    bold = re.search(r"<b>(.*?)</b>", name_cell, re.S)
    site_link = re.search(r'<a href="/site/[^"]*">(.*?)</a>', name_cell, re.S)
    if not bold or not site_link:
        raise common.SourceError("rank-1 row has no system name or site")
    name = _text(bold.group(1))
    site = re.sub(r"\s*\([^)]*\)$", "", _text(site_link.group(1)))
    published = _text(cells[rmax_cols[0]])
    if not re.fullmatch(r"[\d,]+(\.\d+)?", published):
        raise common.SourceError(f"Rmax cell is not a number: {published!r}")
    return name, site, published, unit


def _to_pflops(published, unit):
    try:
        value = Decimal(published.replace(",", "")) / UNIT_DIVISOR[unit]
    except (InvalidOperation, KeyError) as exc:
        raise common.SourceError(f"cannot convert {published} {unit}") from exc
    return format(value.normalize(), "f")


def _yaml_text(value):
    return f"'{value}'" if re.search(r": | #|^[-?:,\[\]{}#&*!|>'\"%@`]|:$", value) else value


def _record_block(edition, value, holder, published, unit):
    url = PAGE.format(edition=edition)
    return (
        f"- date: '{edition.replace('/', '-')}'\n"
        f"  value: {value}\n"
        f"  holder: {_yaml_text(holder)}\n"
        f"  conditions: HPL Rmax, published as {published} {unit}\n"
        f"  status: confirmed\n"
        f"  source: {SOURCE_ID}\n"
        f"  url: {url}\n"
    )


def fetch():
    data = common.load(FRONTIER)
    records = data.get("records") or []
    if not records:
        raise common.SourceError("the frontier has no records to continue from")
    last = max(records, key=lambda r: str(r["date"]))
    last_name = str(last["holder"]).split(",")[0].strip()
    last_value = Decimal(str(last["value"]))

    edition = _next_edition(_edition_of(str(last["date"])))
    new_blocks, messages = [], []
    # Walk forward past editions that exist but do not change the record, stopping at the first
    # missing one. A missing edition means that list has not been published yet.
    while True:
        status, page = _get(PAGE.format(edition=edition))
        if status == 404:
            break
        name, site, published, unit = parse_number_one(page)
        value = _to_pflops(published, unit)
        if name != last_name or Decimal(value) > last_value:
            holder = f"{name}, {site}"
            new_blocks.append(_record_block(edition, value, holder, published, unit))
            messages.append(f"{edition}: {last['holder']} {last['value']} -> {holder} {value} PFlop/s")
            last_name, last_value = name, Decimal(value)
        edition = _next_edition(edition)

    if not new_blocks:
        return []

    text = common.ROOT.joinpath(FRONTIER).read_text(encoding="utf-8")
    marker = "\nevents:"
    if marker in text:
        text = text.replace(marker, "\n" + "".join(new_blocks) + "events:", 1)
    else:
        text = text.rstrip("\n") + "\n" + "".join(new_blocks)
    common.write_if_changed(FRONTIER, text)
    return messages
