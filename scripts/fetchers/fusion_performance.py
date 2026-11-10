"""Check the fusion-performance frontier against the Wurzel & Hsu repository (MIT).

The frontier uses only the data set frozen for the published paper, Phys. Plasmas 32, 112106
(2025): data/experimental_results_published_2025.pkl in swurzel/lawson-criterion-paper. The
repository's working file, data/experimental_results.pkl, holds rows that are not yet in any
refereed version, and those are never imported.

The repository has no releases, tags or manifest that say "a new paper version was published",
and importing a new frozen data set needs a person to check the rebuilt values against the new
paper's tables (see data/datasets/wurzel-hsu-lawson/README.md, "Updating"). So this fetcher
does not import anything. On each run it:

1. checks that the local results.csv still matches the checksum in the dataset README;
2. downloads the frozen 2025 pickle and checks its SHA-256 against the README. A different
   checksum is an error: the published snapshot should never change;
3. looks for signs of a newer published data set or paper: another
   experimental_results_published_<year>.pkl or use_published_<year>_dataset switch in the
   authors' notebook, or a DOI in their README that is not already known. Any of these is
   raised as an error so the refresh reports it and a person imports the new version by hand;
4. loads the working pickle and the frozen pickle with the restricted unpickler from
   scripts/build_wurzel_hsu_results.py (an allow-list of pandas, numpy and datetime classes;
   nothing is ever unpickled without it), and counts the working rows whose id is not in the
   published data set. When the working file has changed since the README last recorded it,
   the README's note on unpublished rows is updated and the count is reported. Frontier
   records are never changed.
"""
import io
import re

from . import common

FRONTIER = "data/frontiers/energy/fusion-performance.yaml"
DATASET = "data/datasets/wurzel-hsu-lawson"
README = f"{DATASET}/README.md"
RAW = "https://raw.githubusercontent.com/swurzel/lawson-criterion-paper/main/"
PUBLISHED_FILE = "data/experimental_results_published_2025.pkl"
PUBLISHED_YEAR = "2025"
WORKING_FILE = "data/experimental_results.pkl"
NOTEBOOK = "lawson-criterion-paper.py"
# DOIs in the authors' README as of 2026-11-09: the 2025 and 2022 papers and the two
# cross-section references. A DOI outside this set may be a new paper version.
KNOWN_DOIS = {
    "10.1063/5.0297357",           # Phys. Plasmas 32, 112106 (2025), the frozen data set
    "10.1063/5.0083990",           # Phys. Plasmas 29, 062103 (2022)
    "10.1088/0029-5515/32/4/I07",  # Bosch & Hale 1992
    "10.1088/0029-5515/40/4/310",  # Nevins & Swain 2000
}
PUBLISHED_ROWS = 124

UNPUBLISHED_LINE = re.compile(
    r"(?m)^- The repository's ongoing, unpublished data set \(`data/experimental_results\.pkl`, "
    r"SHA-256 ([0-9a-f]{64})\)\. It adds (\d+) rows: [^\n]*$")


def _readme_value(text, label):
    m = re.search(r"(?m)^\|\s*" + re.escape(label) + r"\s*\|\s*([0-9a-f]{64})\b", text)
    if not m:
        raise common.SourceError(f"no '{label}' checksum in {README}")
    return m.group(1)


def _load_pickle(raw, name):
    # Imported here so the module loads without pandas; the build script holds the allow-list.
    from build_wurzel_hsu_results import RestrictedUnpickler
    try:
        df = RestrictedUnpickler(io.BytesIO(raw)).load()
    except Exception as exc:  # noqa: BLE001  (includes refusals by the allow-list)
        raise common.SourceError(f"could not safely load {name}: {exc}") from exc
    if not hasattr(df, "columns") or "id" not in df.columns or not df["id"].is_unique:
        raise common.SourceError(f"{name} is not a data frame with a unique 'id' column")
    return df


def _check_for_new_version():
    notebook = common.get(RAW + NOTEBOOK).decode("utf-8", "replace")
    years = set(re.findall(r"experimental_results_published_(\d{4})\.pkl", notebook))
    years |= set(re.findall(r"use_published_(\d{4})_dataset", notebook))
    if PUBLISHED_YEAR not in years:
        raise common.SourceError(f"{NOTEBOOK} no longer refers to the published {PUBLISHED_YEAR} data set; "
                                 "check the repository by hand")
    if years - {PUBLISHED_YEAR}:
        raise common.SourceError(
            f"{NOTEBOOK} refers to a published data set for {', '.join(sorted(years - {PUBLISHED_YEAR}))}. "
            "A new frozen data set may be out: import it by hand as described in "
            f"{README} (Updating), then update this fetcher")

    readme = common.get(RAW + "README.md").decode("utf-8", "replace")
    dois = {d.rstrip(".,;") for d in re.findall(r"10\.\d{4,9}/[^\s)\]>\"']+", readme)}
    if "10.1063/5.0297357" not in dois:
        raise common.SourceError("the authors' README no longer cites the 2025 paper; check the repository by hand")
    if dois - KNOWN_DOIS:
        raise common.SourceError(
            f"the authors' README cites new DOIs: {', '.join(sorted(dois - KNOWN_DOIS))}. If this is a new "
            f"paper version, import its frozen data set by hand ({README}, Updating); otherwise add the DOI "
            "to KNOWN_DOIS in this fetcher")


def _describe(row):
    date = row.get("Date")
    if date is None or str(date) in ("", "nan", "NaT", "None"):
        year = row.get("Year")
        date = str(int(year)) if year is not None and str(year) != "nan" else "undated"
    return f"{row.get('Project Displayname')} {date} (shot {row.get('Shot')}, id {int(row['id'])})"


def fetch():
    readme = (common.ROOT / README).read_text(encoding="utf-8")
    csv_bytes = (common.ROOT / DATASET / "results.csv").read_bytes()
    if common.sha256(csv_bytes) != _readme_value(readme, "results.csv SHA-256"):
        raise common.SourceError(f"{DATASET}/results.csv does not match the checksum in its README")

    published_raw = common.get(RAW + PUBLISHED_FILE)
    expected = _readme_value(readme, "Original file SHA-256")
    if common.sha256(published_raw) != expected:
        raise common.SourceError(
            f"{PUBLISHED_FILE} changed upstream (SHA-256 {common.sha256(published_raw)}, expected {expected}). "
            "The published snapshot should not change; review it and rebuild by hand")

    _check_for_new_version()

    published = _load_pickle(published_raw, PUBLISHED_FILE)
    if len(published) != PUBLISHED_ROWS:
        raise common.SourceError(f"{PUBLISHED_FILE} has {len(published)} rows, expected {PUBLISHED_ROWS}")

    working_raw = common.get(RAW + WORKING_FILE)
    working = _load_pickle(working_raw, WORKING_FILE)
    if len(working) < PUBLISHED_ROWS // 2:
        raise common.SourceError(f"{WORKING_FILE} has only {len(working)} rows")
    unpublished = working[~working["id"].isin(set(published["id"]))]
    count = len(unpublished)
    working_sha = common.sha256(working_raw)

    m = UNPUBLISHED_LINE.search(readme)
    if not m:
        raise common.SourceError(f"could not find the note on unpublished rows in {README}")
    old_sha, old_count = m.group(1), int(m.group(2))
    print(f"fusion_performance: frozen {PUBLISHED_YEAR} data set unchanged ({len(published)} rows); "
          f"working data set has {len(working)} rows, {count} not in the published data set")
    if working_sha == old_sha:
        return []

    rows = [_describe(r) for _, r in unpublished.sort_values("id").iterrows()]
    line = (f"- The repository's ongoing, unpublished data set (`data/experimental_results.pkl`, "
            f"SHA-256 {working_sha}). It adds {count} rows: {'; '.join(rows)}. These were left out because "
            f"they are not yet in a refereed version (checked {common.today()}).")
    common.write_if_changed(README, readme[:m.start()] + line + readme[m.end():])
    return [f"Authors' unpublished working data set changed: {old_count} -> {count} rows not in the "
            f"published {PUBLISHED_YEAR} data set (not imported; frozen data set unchanged)"]
