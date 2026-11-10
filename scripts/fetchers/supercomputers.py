"""Diagnostic fetcher for the TOP500 frontier. Prints what it reads and writes nothing."""
import re
import urllib.error
import urllib.request

from . import common

FRONTIER = "data/frontiers/computing/supercomputers.yaml"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": common.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}", ""


def fetch():
    status, robots = _get("https://www.top500.org/robots.txt")
    print(f"robots.txt status: {status}")
    print(robots[:3000])

    status, page = _get("https://www.top500.org/lists/top500/2026/11/")
    print(f"list page 2026/11 status: {status}, length: {len(page)}")
    if page:
        row = re.search(r"<tr[^>]*>(?:(?!</tr>).)*?<td[^>]*>\s*1\s*</td>.*?</tr>", page, re.S)
        print("rank-1 row:" if row else "no rank-1 row matched")
        print((row.group(0) if row else page[:1500])[:1500])
    return []
