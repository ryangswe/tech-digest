"""Feedback: parse ticked boxes, summarise state/feedback.jsonl, decide if the weekly review is due."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

TICK_RE = re.compile(r"^\s*[-*] \[[xX]\] (👍|👎)\s.*?<!-- id:([0-9a-f]{10}) -->", re.M)
WEEKLY_MIN_GAP_DAYS = 6
SIGNALS = {"vote", "reaction", "comment"}


def parse_ticks(body: str) -> list[tuple[int, str]]:
    """[(+1 | -1, item id)] for every ticked box; 👍 and 👎 both ticked cancel out."""
    votes: dict[str, int] = {}
    for emoji, iid in TICK_RE.findall(body or ""):
        votes[iid] = votes.get(iid, 0) + (1 if emoji == "👍" else -1)
    return [(v, iid) for iid, v in votes.items() if v]


def load_lines(path: Path) -> list[dict]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return [json.loads(ln) for ln in text.splitlines() if ln.strip()]


def append_lines(path: Path, lines: list[dict]) -> None:
    if not lines:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for ln in lines:
            f.write(json.dumps(ln, ensure_ascii=False, sort_keys=True) + "\n")


def summary(lines: list[dict], today: str, days: int = 30) -> str:
    """Markdown for the Claude step: what the owner liked and disliked recently."""
    cutoff = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    recent = [ln for ln in lines if ln.get("digest", "") >= cutoff and ln.get("kind") in SIGNALS]
    if not recent:
        return f"No feedback in the last {days} days."
    out = [f"Feedback from the last {days} days ({len(recent)} signals)."]
    votes = [ln for ln in recent if ln["kind"] == "vote"]
    by_src: dict[str, Counter] = defaultdict(Counter)
    for v in votes:
        by_src[v.get("source", "?")]["up" if v["vote"] > 0 else "down"] += 1
    if by_src:
        out += ["", "By source (👍/👎):"]
        out += [f"- {s}: {c['up']}/{c['down']}" for s, c in
                sorted(by_src.items(), key=lambda kv: -(kv[1]["up"] + kv[1]["down"]))]
    for sign, head in ((1, "Liked"), (-1, "Disliked")):
        picked = [v for v in votes if v["vote"] == sign]
        if picked:
            out += ["", f"{head}:"] + [f"- {v.get('title', v['id'])} ({v.get('source', '?')}, {v['digest']})"
                                       for v in picked[-25:]]
    reactions = [ln for ln in recent if ln["kind"] == "reaction"]
    if reactions:
        out += ["", "Whole-digest reactions: " + ", ".join(
            f"{ln['digest']} {'👍' if ln['vote'] > 0 else '👎'}" for ln in reactions[-14:])]
    comments = [ln for ln in recent if ln["kind"] == "comment"]
    if comments:
        out += ["", "Comments (the owner's own words):"]
        out += [f"- {ln['digest']}: " + re.sub(r"\s+", " ", ln["text"])[:400] for ln in comments[-20:]]
    return "\n".join(out)


def weekly_status(today: str, weekly: dict, lines: list[dict]) -> tuple[bool, str]:
    last = weekly.get("last_proposal")
    new = [ln for ln in lines if ln.get("kind") in SIGNALS
           and (not last or ln.get("harvested", ln.get("digest", "")) > last)]
    if not new:
        return False, "no feedback since the last proposal"
    d = date.fromisoformat(today)
    if last and (d - date.fromisoformat(last)).days < WEEKLY_MIN_GAP_DAYS:
        return False, f"last proposal was {last}"
    if d.weekday() != 0 and not (last and (d - date.fromisoformat(last)).days >= 8):
        return False, "the weekly review runs on Mondays"
    return True, f"{len(new)} new feedback signal(s) since {last or 'the start'}"
