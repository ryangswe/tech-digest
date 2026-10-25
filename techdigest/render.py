"""picks + candidates -> digest/DATE.json -> digest/DATE.md (also the issue body).

`to_markdown` is a pure function of the digest JSON, so the delivery Action can re-render the
JSON and refuse a Markdown file that does not match it.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from . import picks as P
from .cards import validate_cards_structure

CARDS_MAX = 6
KIND_LABEL = {"try": "Try", "adopt": "Adopt", "watch": "Watch", "read-later": "Read later"}
def card_rank(c: dict) -> tuple:
    """Flagged sources last (they tried to steer agents), then your 🔍 requests first, then
    try/adopt before watch/read-later, surer and smaller steps first."""
    from .cards import CONFIDENCE, EFFORTS, KINDS
    return (bool(c.get("flagged")), not c.get("asked"), KINDS.index(c["kind"]), CONFIDENCE.index(c["confidence"]),
            EFFORTS.index(c["effort"]))


FLAG_NOTE = " ⚠️ The source contained text aimed at AI agents; the reader ignored it."
from .state import write_json

ID_COMMENT = re.compile(r"<!-- id:([0-9a-f]{10}) -->")


class RenderError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


def digest_title(day: str) -> str:
    d = date.fromisoformat(day)
    return f"☕ Tech Digest — {d:%a} {d.day} {d:%b} {d.year}"


def _link_fields(c: dict) -> dict:
    return {
        "title": c["title"], "url": c["url"], "source": c["source"],
        "source_name": c["source_name"], "link_name": c.get("link_name", c["source_name"]),
        "discussions": c.get("discussions", []),
    }


def build_digest(picks: dict, candidates_doc: dict, report: dict | None = None,
                 ranker: str = "claude", cards: list[dict] | None = None) -> dict:
    errors = P.validate_picks(picks, candidates_doc)
    if errors:
        raise RenderError(errors)
    by_id = {c["id"]: c for c in candidates_doc["candidates"]}
    report = report or {}
    sources = report.get("sources", {})
    out = {
        "schema_version": P.SCHEMA_VERSION,
        "date": picks["date"],
        "title": digest_title(picks["date"]),
        "opener": picks["opener"].strip(),
        "ranker": ranker,
    }
    for section, fields in P.SECTION_FIELDS.items():
        out[section] = [
            {"id": e["id"], **{f: e[f].strip() for f in fields[1:]}, **_link_fields(by_id[e["id"]])}
            for e in picks.get(section, [])
        ]
    cards = cards or []
    cerrs = validate_cards_structure(cards)
    if cerrs:
        raise RenderError(cerrs)
    out["cards"] = sorted(cards, key=card_rank)[:CARDS_MAX]
    out["stats"] = {
        "candidates": len(by_id),
        "sources_ok": sum(1 for s in sources.values() if s.get("ok")),
        "sources_total": len(sources),
        "failed": [{"id": sid, "name": s.get("name", sid), "error": s.get("error", "")}
                   for sid, s in sources.items() if not s.get("ok")],
        "quiet": list(report.get("quiet", [])),
        "baseline": [s.get("name", sid) for sid, s in sources.items() if s.get("bootstrapped")],
    }
    return out


def validate_digest(d: dict) -> list[str]:
    """Structural check of a digest JSON on its own (used by the delivery Action)."""
    errs = []
    if d.get("schema_version") not in (1, P.SCHEMA_VERSION):
        errs.append(f"schema_version must be 1 or {P.SCHEMA_VERSION}")
    errs += validate_cards_structure(d.get("cards", []))
    if len(d.get("cards", [])) > CARDS_MAX:
        errs.append(f"at most {CARDS_MAX} cards")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(d.get("date", ""))):
        errs.append("date must be YYYY-MM-DD")
    errs += P.text_errors("digest", "opener", d.get("opener"))
    ids = []
    for section, fields in P.SECTION_FIELDS.items():
        for n, e in enumerate(d.get(section, []), 1):
            where = f"{section}[{n}]"
            ids.append(e.get("id"))
            if not re.match(r"^https?://", str(e.get("url", ""))):
                errs.append(f"{where}: url must be http(s)")
            for f in fields[1:]:
                errs += P.text_errors(where, f, e.get(f))
    if len(ids) != len(set(ids)):
        errs.append("an item id appears twice")
    if len(d.get("top", [])) > P.TOP_N or len(d.get("skim", [])) > P.SKIM_MAX \
            or len(d.get("tools", [])) > P.TOOLS_MAX:
        errs.append("too many items in a section")
    return errs


# --- Markdown ------------------------------------------------------------------------------

ZWJ = "\u2060"  # word joiner: stops GitHub turning @name and #123 into pings and cross-links


def _esc(text: str) -> str:
    text = re.sub(r"([\[\]`*_\\])", r"\\\1", text).replace("<", "&lt;")
    return re.sub(r"([@#])(?=[A-Za-z0-9])", "\\1" + ZWJ, text)


def _href(url: str) -> str:
    return url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def _links(e: dict) -> str:
    parts = [f"[{_esc(e.get('link_name') or e['source_name'])}]({_href(e['url'])})"]
    for d in e.get("discussions", []):
        if d.get("url") and d["url"] != e["url"]:
            label = d.get("name", "Discussion")
            if d.get("comments"):
                label += f", {d['comments']} comments"
            parts.append(f"[{_esc(label)}]({_href(d['url'])})")
    return " · ".join(parts)


def _label(text: str, n: int = 90) -> str:
    text = re.sub(r"\s+", " ", text).replace("<!--", "").replace("-->", "").strip()
    return _esc(text if len(text) <= n else text[: n - 1].rstrip() + "…")


def to_markdown(d: dict) -> str:
    L = [f"# {d['title']}", "", f"_{_esc(d['opener'])}_", ""]
    L += ["## 🏆 Top 3", ""]
    if not d["top"]:
        L += ["_A quiet day: nothing new from your sources._", ""]
    for n, e in enumerate(d["top"], 1):
        L += [f"### {n}. {_esc(e['headline'])}", "", _esc(e["summary"]), "",
              f"**Why it matters to you:** {_esc(e['why'])}", "", _links(e), ""]
    if d.get("cards"):
        L += ["## 🧪 Worth trying", ""]
        for c in d["cards"]:
            asked = "🔍 " if c.get("asked") else ""
            fits = ", ".join(c["fits"])
            line = (f"- {asked}**{KIND_LABEL[c['kind']]} · {c['effort']}**: {_esc(c['next_step'])} "
                    f"_{_esc(c['title'])}_ · fits {_esc(fits)} "
                    f"([{_esc(c['source_name'] or 'Source')}]({_href(c['url'])}))")
            L.append(line + (FLAG_NOTE if c.get("flagged") else ""))
        L += [""]
    L += ["## 👀 Worth a skim", ""]
    L += [f"- {_esc(e['line'])} ({_links(e)})" for e in d["skim"]] or ["_Nothing else today._"]
    L += ["", "## 🔧 Changed in my tools", ""]
    L += [f"- {_esc(e['line'])} ({_links(e)})" for e in d["tools"]] or \
        ["_Nothing changed in your tools today._"]
    items = [(e.get("headline") or f"{e['source_name']}: {e['title']}", e["id"])
             for s in ("top", "skim", "tools") for e in d[s]]
    if items:
        L += ["", "<details><summary>👍 / 👎 / 🔍 — tick any. 🔍 means dig in: a reviewer reads it "
              "in full tomorrow and says what's worth trying</summary>", ""]
        for label, iid in items:
            L.append(f"- [ ] 👍 {_label(label)} <!-- id:{iid} -->")
            L.append(f"- [ ] 👎 {_label(label)} <!-- id:{iid} -->")
            L.append(f"- [ ] 🔍 {_label(label)} <!-- id:{iid} -->")
        L += ["", "</details>"]
    st = d["stats"]
    foot = f"{st['candidates']} new items from {st['sources_ok']}/{st['sources_total']} sources"
    if st["failed"]:
        by_err: dict[str, list[str]] = {}
        for f in st["failed"]:
            by_err.setdefault(f["error"], []).append(f["name"])
        foot += " · failed today: " + "; ".join(
            ", ".join(names) + (f" ({err})" if err else "") for err, names in by_err.items())
    if st.get("baseline"):
        foot += " · first look, so today's links were recorded, not shown: " + ", ".join(st["baseline"])
    if st["quiet"]:
        foot += " · no items for 3+ runs: " + ", ".join(st["quiet"])
    foot += " · ranked by " + ("Claude" if d.get("ranker") == "claude" else "the offline keyword ranker (dry run)")
    L += ["", f"<sub>{_esc(foot)}</sub>", ""]
    return "\n".join(L)


def write_digest(d: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    jpath, mpath = out_dir / f"{d['date']}.json", out_dir / f"{d['date']}.md"
    write_json(jpath, d)
    mpath.write_text(to_markdown(d), encoding="utf-8")
    return jpath, mpath


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
