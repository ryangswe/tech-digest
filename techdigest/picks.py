"""The picks contract: the only thing the Claude step writes (build/picks.json).

    {
      "date": "YYYY-MM-DD",                       # must equal candidates.json's date
      "opener": "one Morning Brew-style line",
      "top":   [{"id", "headline", "summary", "why"}],   # exactly min(3, #candidates)
      "skim":  [{"id", "line"}],                          # 0-10
      "tools": [{"id", "line"}]                           # 0-6, only `tool`-tagged candidates
    }

Text fields are plain prose: no URLs, no Markdown links, no HTML, no line breaks. Links are
added by the renderer from the fetched data. Change this module, prompts/daily.md and the tests
together.
"""

from __future__ import annotations

import re

from .text import word_count

SCHEMA_VERSION = 1
TOP_N, SKIM_MAX, TOOLS_MAX = 3, 10, 6
WORDS = {"opener": 40, "headline": 14, "summary": 80, "why": 50, "line": 40}
TOTAL_WORDS = 1100  # about 5 minutes of reading
SECTION_FIELDS = {
    "top": ("id", "headline", "summary", "why"),
    "skim": ("id", "line"),
    "tools": ("id", "line"),
}
URL_RE = re.compile(r"https?://|www\.|\]\(|\b[a-z0-9-]+\.(com|org|io|dev|ai|net)/", re.I)


def text_errors(where: str, field: str, value) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{where}.{field}: must be a non-empty string"]
    errs = []
    if URL_RE.search(value):
        errs.append(f"{where}.{field}: contains a URL or link; links come from the source data")
    if "<" in value or "\n" in value:
        errs.append(f"{where}.{field}: no HTML and no line breaks")
    if value.lstrip().startswith(("#", "-", "* ", ">")):
        errs.append(f"{where}.{field}: plain prose only, no Markdown block syntax")
    limit = WORDS.get(field)
    if limit and word_count(value) > limit:
        errs.append(f"{where}.{field}: {word_count(value)} words, over the {limit}-word limit")
    return errs


def validate_picks(picks: dict, candidates_doc: dict) -> list[str]:
    """Every reason `picks` is unacceptable, as messages Claude can act on. Empty = valid."""
    if not isinstance(picks, dict):
        return ["picks: must be a JSON object"]
    errs: list[str] = []
    allowed = {"date", "opener", *SECTION_FIELDS}
    extra = set(picks) - allowed
    if extra:
        errs.append(f"picks: unknown field(s) {sorted(extra)}; allowed: {sorted(allowed)}")
    if picks.get("date") != candidates_doc.get("date"):
        errs.append(f"date: must be {candidates_doc.get('date')!r} (from candidates.json), "
                    f"got {picks.get('date')!r}")
    errs += text_errors("picks", "opener", picks.get("opener"))
    by_id = {c["id"]: c for c in candidates_doc.get("candidates", [])}
    used: set[str] = set()
    total = word_count(picks.get("opener") or "") if isinstance(picks.get("opener"), str) else 0
    for section, fields in SECTION_FIELDS.items():
        entries = picks.get(section, [])
        if not isinstance(entries, list):
            errs.append(f"{section}: must be a list")
            continue
        for n, e in enumerate(entries, 1):
            where = f"{section}[{n}]"
            if not isinstance(e, dict):
                errs.append(f"{where}: must be an object")
                continue
            extra = set(e) - set(fields)
            if extra:
                errs.append(f"{where}: unknown field(s) {sorted(extra)}; allowed: {list(fields)}")
            cid = e.get("id")
            if cid not in by_id:
                errs.append(f"{where}.id: {cid!r} is not a candidate id")
            elif cid in used:
                errs.append(f"{where}.id: {cid!r} is already used; each item appears once")
            else:
                used.add(cid)
                if section == "tools" and "tool" not in by_id[cid].get("tags", []):
                    errs.append(f"{where}.id: {cid!r} is not from a `tool` source; put it in "
                                "top or skim instead")
            for f in fields[1:]:
                errs += text_errors(where, f, e.get(f))
                if isinstance(e.get(f), str):
                    total += word_count(e[f])
    want_top = min(TOP_N, len(by_id))
    if isinstance(picks.get("top"), list) and len(picks["top"]) != want_top:
        errs.append(f"top: needs exactly {want_top} items, got {len(picks['top'])}")
    if isinstance(picks.get("skim"), list) and len(picks["skim"]) > SKIM_MAX:
        errs.append(f"skim: at most {SKIM_MAX} items, got {len(picks['skim'])}")
    if isinstance(picks.get("tools"), list) and len(picks["tools"]) > TOOLS_MAX:
        errs.append(f"tools: at most {TOOLS_MAX} items, got {len(picks['tools'])}")
    if total > TOTAL_WORDS:
        errs.append(f"length: {total} words, over the {TOTAL_WORDS}-word (5-minute) budget; "
                    "cut skim items or shorten summaries")
    return errs
