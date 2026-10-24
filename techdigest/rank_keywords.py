"""Offline stand-in for the Claude step: rank by keyword weights and HN points.

Used by `dry-run` and the tests. Its text is the source's own title and summary, cut short.
"""

from __future__ import annotations

import math
import re

from . import picks as P
from .text import matches_any, truncate_words

URLISH = re.compile(r"\S*(https?://|www\.)\S*|\S+\.(com|org|io|dev|ai|net)/\S*", re.I)


def _plain(text: str) -> str:
    text = URLISH.sub("", text or "")
    text = text.replace("<", "").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip().lstrip("#->* ").strip() or "(no summary)"


def score(c: dict, keywords: list[dict]) -> float:
    text = f"{c['title']} {c.get('summary', '')}"
    terms = {k["term"]: k.get("weight", 1) for k in keywords}
    s = sum(terms[t] for t in matches_any(text, list(terms)))
    return s + math.log10(1 + (c.get("points") or 0))


def keyword_picks(candidates_doc: dict, keywords: list[dict]) -> dict:
    cands = sorted(candidates_doc["candidates"], key=lambda c: -score(c, keywords))
    tools = [c for c in cands if "tool" in c.get("tags", [])]
    top = [c for c in cands if c not in tools][: P.TOP_N]
    if len(top) < min(P.TOP_N, len(cands)):  # only tool items left: let them fill the top
        top += [c for c in tools if c not in top][: P.TOP_N - len(top)]
    rest = [c for c in cands if c not in top]
    tool_picks = [c for c in rest if c in tools][: P.TOOLS_MAX]
    skim = [c for c in rest if c not in tool_picks][: P.SKIM_MAX]

    def why(c: dict) -> str:
        hits = matches_any(f"{c['title']} {c.get('summary', '')}", [k["term"] for k in keywords])
        return (f"Matches your interests: {', '.join(hits[:3])}." if hits
                else "High engagement among today's new items.")

    return {
        "date": candidates_doc["date"],
        "opener": "Dry run: these picks come from saved fixtures and a keyword ranker, not Claude.",
        "top": [{"id": c["id"], "headline": truncate_words(_plain(c["title"]), P.WORDS["headline"]),
                 "summary": truncate_words(_plain(c.get("summary") or c["title"]), 60),
                 "why": why(c)} for c in top],
        "skim": [{"id": c["id"], "line": truncate_words(_plain(c["title"]), 30)} for c in skim],
        "tools": [{"id": c["id"], "line": truncate_words(
            _plain(f"{c['source_name']} {c['title']}: {c.get('summary') or ''}".rstrip(': ')), 30)} for c in tool_picks],
    }
