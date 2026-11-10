"""Shared helpers for the automatic data refresh.

Each fetcher module in this folder refreshes one frontier from its machine-readable
source. A fetcher defines:

    FRONTIER = "data/frontiers/<domain>/<id>.yaml"   # the file it may change
    def fetch() -> list[str]:                        # change messages; [] if nothing new

A fetcher downloads its source, rewrites the dataset copy and/or the frontier file
(usually by calling the frontier's import script), and returns one short line per change.
It raises an exception if the source cannot be read or looks wrong; the refresh then
reverts anything that fetcher touched and reports the failure. It never guesses.
"""
import datetime as dt
import hashlib
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from validate import load_yaml  # noqa: E402  (keeps dates as strings)

USER_AGENT = "frontier-data-refresh (+https://github.com/000xx/frontier)"


class SourceError(RuntimeError):
    """The source could not be read, or returned something that does not look right."""


def get(url, timeout=90):
    """Download a URL and return its bytes. Raises SourceError on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        raise SourceError(f"could not download {url}: {exc}") from exc


def today():
    return dt.date.today().isoformat()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return load_yaml(ROOT / path)


def write_if_changed(path, data):
    """Write bytes or text to a file under ROOT. Returns True if the content changed."""
    target = ROOT / path
    new = data.encode("utf-8") if isinstance(data, str) else data
    old = target.read_bytes() if target.exists() else None
    if old == new:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(new)
    return True


def set_last_checked(path, date=None):
    """Set update.last_checked in a frontier file without reformatting the rest of it."""
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    new, n = re.subn(r"(?m)^(\s+last_checked:\s*)['\"]?\d{4}-\d{2}-\d{2}['\"]?\s*$",
                     lambda m: f"{m.group(1)}'{date or today()}'", text, count=1)
    if n != 1:
        raise RuntimeError(f"could not find update.last_checked in {path}")
    if new != text:
        target.write_text(new, encoding="utf-8")


def set_readme_row(path, label, value):
    """Replace the value cell of a two-column markdown table row whose first cell is `label`."""
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    pattern = re.compile(r"(?m)^\|[ \t]*" + re.escape(label) + r"[ \t]*\|[^\n]*\|[ \t]*$")
    if not pattern.search(text):
        raise RuntimeError(f"no '{label}' row in {path}")
    target.write_text(pattern.sub(f"| {label} | {value} |", text, count=1), encoding="utf-8")


def run_script(*args):
    """Run a repository script with the current Python and return its stdout."""
    result = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, args))} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout
