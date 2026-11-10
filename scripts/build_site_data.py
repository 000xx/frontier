"""Build site/js/data.js from the data files in this repository.

Usage: python scripts/build_site_data.py

Every file under data/frontiers/ becomes a page on the site. The site draws a
frontier from the blocks its file holds (records, observations, items, stages
and candidates, events, reading, sources), so a new frontier needs no site
change. Site-level choices that are not data live in site/config.json.
The output is generated: do not edit it or commit it.
"""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "js" / "data.js"


def one_line(text):
    return " ".join(str(text or "").split())


def dataset_credits(text):
    """Credit lines and required notices from each dataset NOTICE.md the frontier file mentions.

    A NOTICE.md states its credit in one of three ways, tried in this order: a
    "## Required credit" section, a sentence saying charts should carry the line "...", or a plain
    "Credit:" paragraph. Lines starting with "> " outside the
    credit section are a notice the source requires to be shown in full.
    """
    out, seen = [], set()
    for ds in re.findall(r"data/datasets/([\w-]+)", text):
        path = ROOT / "data" / "datasets" / ds / "NOTICE.md"
        if ds in seen or not path.exists():
            continue
        seen.add(ds)
        notice = path.read_text(encoding="utf-8")
        section = re.search(r"^## Required credit\s*\n(.*?)(?=^## |\Z)", notice, re.M | re.S)
        para = re.search(r"^Credit:\s*(.+)$", notice, re.M)
        line = ""
        if section:
            body = section.group(1)
            quoted = [l[2:] for l in body.split("\n") if l.startswith("> ")]
            line = one_line(" ".join(quoted)) if quoted else one_line(body.strip().split("\n\n")[0])
            notice = notice.replace(body, "")
        else:
            q = re.search(r'carry the line[^"“]*["“]([^"”]+)["”]', notice)
            line = q.group(1) if q else one_line(para.group(1)) if para else ""
        required = "\n".join(l[2:] for l in notice.split("\n") if l.startswith("> ")).strip()
        out.append({"dataset": ds, "line": line, "notice": required})
    return out


def by_series(rows, make):
    out = {}
    for r in rows or []:
        if r.get("value") is None:
            continue
        out.setdefault(r.get("series") or "_", []).append(make(r))
    for v in out.values():
        v.sort(key=lambda row: row[0])
    return out


def build():
    domains = yaml.safe_load((ROOT / "data" / "domains.yaml").read_text(encoding="utf-8"))
    domain_name = {d["id"]: d["name"] for d in domains}
    config = json.loads((ROOT / "site" / "config.json").read_text(encoding="utf-8"))

    frontiers = []
    for path in sorted((ROOT / "data" / "frontiers").rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        d = yaml.safe_load(text)
        metric = d.get("metric") or {}
        sources = d.get("sources") or []
        frontiers.append({
            "id": d["id"],
            "title": d["title"],
            "domain": domain_name.get(d.get("domain"), d.get("domain", "")),
            "subfield": d.get("subfield", ""),
            "dataStatus": d.get("status", ""),
            "summary": one_line(d.get("summary")),
            "about": {"what": one_line((d.get("about") or {}).get("what")), "why": one_line((d.get("about") or {}).get("why"))},
            "metric": {
                "name": metric.get("name", ""), "unit": metric.get("unit", ""),
                "direction": metric.get("direction", "higher"), "scale": metric.get("scale", "linear"),
                "target": metric.get("target"), "limit": metric.get("limit"), "axes": metric.get("axes") or [],
            },
            "explainer": one_line(metric.get("explainer")),
            "shape": (d.get("chart") or {}).get("primary", ""),
            "series": d.get("series") or [],
            "records": by_series(d.get("records"), lambda r: [
                str(r["date"]), r["value"], r.get("holder") or "", r.get("conditions") or "",
                r.get("status") or "", r.get("source") or "", r.get("extra") or None]),
            "observations": by_series(d.get("observations"), lambda r: [
                str(r["date"]), r["value"], r.get("low"), r.get("high"), r.get("source") or "", one_line(r.get("note"))]),
            "items": [[str(i["id"]), i["label"], i.get("group") or "", i["status"], i.get("status_detail") or "",
                       str(i.get("date_done") or ""), i.get("url") or "", i.get("ai_involvement") or ""]
                      for i in d.get("items") or []],
            "stages": d.get("stages") or [],
            "candidates": [{"name": c["name"], "developer": c.get("developer") or "", "kind": c.get("kind") or "",
                            "stage": c.get("stage") or "", "key": one_line(c.get("key_result")), "url": c.get("url") or ""}
                           for c in d.get("candidates") or []],
            "events": [{"date": str(e["date"]), "kind": e.get("kind") or "", "title": e["title"],
                        "why": one_line(e.get("why_it_matters")), "url": e.get("url")} for e in d.get("events") or []],
            "reading": [{"title": r["title"], "author": r.get("author") or "", "kind": r.get("kind") or "",
                         "url": r.get("url"), "note": one_line(r.get("note"))} for r in d.get("reading") or []],
            "sources": [{"id": s["id"], "name": s["name"], "url": s.get("url"), "kind": s.get("kind")} for s in sources],
            "credits": dataset_credits(text),
            "lastChecked": str((d.get("update") or {}).get("last_checked", "")),
            "featured": (config.get("featured") or {}).get(d["id"]),
        })

    data = {
        "site": {"name": config.get("name", "Frontier in Numbers"), "lead": config.get("lead")},
        "domains": [d["name"] for d in domains],
        "planned": config.get("planned") or [],
        "frontiers": frontiers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "/* Generated by scripts/build_site_data.py. Do not edit by hand. */\n"
        "window.FRONTIER_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(frontiers)} frontiers, {OUT.stat().st_size // 1024} KB")
    for f in frontiers:
        blocks = [k for k in ("records", "observations", "items", "candidates") if f[k]]
        print(f"  {f['id']}: {f['shape']}; blocks: {', '.join(blocks) or 'none'}; credits: {[c['line'][:90] for c in f['credits']]}")


if __name__ == "__main__":
    build()
