"""The weekly "Try this" issue, built by the delivery workflow on Mondays. No Claude involved:
it ranks cards that were already validated when their digests were made.

    prepare  harvest last week's try-this ticks, close nothing yet, build reviews/<week>.{json,md},
             mark backlog queue items as shown
    publish  open this week's issue (once), close earlier ones
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

from .cards import CONFIDENCE, EFFORTS, KINDS
from .feedback import append_lines, load_lines
from .render import KIND_LABEL, _esc, _href
from .state import write_json

LABEL = "try-this"
MARKER_RE = re.compile(r"<!-- try-this:(\d{4}-W\d{2}) -->")
TICK_RE = re.compile(r"^\s*[-*] \[[xX]\] (✅|⏳|🙅)\s.*?<!-- card:([0-9a-f]{10}) -->", re.M)
TICK_KIND = {"✅": "tried", "⏳": "later", "🙅": "not_for_me"}
FROM_BACKLOG, TOTAL = 5, 10


def week_id(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def parse_ticks(body: str) -> list[tuple[str, str]]:
    """[(tried | later | not_for_me, card id)]; the last box ticked for a card wins."""
    out: dict[str, str] = {}
    for emoji, cid in TICK_RE.findall(body or ""):
        out[cid] = TICK_KIND[emoji]
    return list((k, cid) for cid, k in out.items())


def _week_cards(repo: Path, monday: date) -> list[dict]:
    cards: dict[str, dict] = {}
    for n in range(7, 0, -1):
        day = (monday - timedelta(days=n)).isoformat()
        p = repo / f"digest/{day}.json"
        if p.exists():
            for c in json.loads(p.read_text(encoding="utf-8")).get("cards", []):
                cards.setdefault(c["id"], {**c, "from": f"digest {day}"})
    return list(cards.values())


def _score(c: dict, votes: dict[str, int], asked: set[str]) -> tuple:
    return (-(votes.get(c["id"], 0) + (2 if c["id"] in asked or c.get("asked") else 0)),
            KINDS.index(c["kind"]), CONFIDENCE.index(c["confidence"]), EFFORTS.index(c["effort"]))


def build(repo: Path, today: str) -> dict | None:
    """reviews/<week>.json content for the week starting `today` (a Monday), or None if empty."""
    repo = Path(repo)
    monday = date.fromisoformat(today)
    lines = load_lines(repo / "state/feedback.jsonl")
    votes: dict[str, int] = {}
    for ln in lines:
        if ln.get("kind") == "vote":
            votes[ln["id"]] = votes.get(ln["id"], 0) + 2 * ln["vote"]
    asked = {ln["id"] for ln in lines if ln.get("kind") == "dig"}
    closed = {ln["id"] for ln in lines if ln.get("kind") in ("tried", "not_for_me")}
    reviews = {p.stem: json.loads(p.read_text()).get("cards", [])
               for p in (repo / "reviews").glob("*.json") if p.stem < week_id(monday)}
    shown_before = {c["id"] for cards in reviews.values() for c in cards}
    # "later" brings a card back once: only if no review since the one it was ticked on showed it
    ticked_week = {ln["id"]: ln["digest"] for ln in lines if ln.get("kind") == "later"}
    later = {cid for cid, wk in ticked_week.items()
             if not any(stem > wk and any(c["id"] == cid for c in cards) for stem, cards in reviews.items())}

    pool = [c for c in _week_cards(repo, monday) if c["id"] not in closed and votes.get(c["id"], 0) >= 0]
    for stem in sorted(reviews):  # "later" cards come back once
        for c in reviews[stem]:
            if c["id"] in later and c["id"] not in closed and c["id"] not in {x["id"] for x in pool}:
                pool.append({**c, "from": "you said later"})
    pool = [c for c in pool if c["id"] not in shown_before or c.get("from") == "you said later"]
    pool.sort(key=lambda c: _score(c, votes, asked))

    queue_path = repo / "backlog/queue.json"
    queue = json.loads(queue_path.read_text()) if queue_path.exists() else []
    waiting = [q for q in queue if q.get("status", "queued") == "queued" and q["id"] not in closed]
    from_backlog = waiting[:FROM_BACKLOG]
    picked = pool[: TOTAL - len(from_backlog)]  # the week fills whatever the backlog leaves
    cards = picked + [{**q, "from": "your bookmarks"} for q in from_backlog]
    if not cards:
        return None
    return {"schema_version": 1, "week": week_id(monday), "date": today,
            "title": f"🧪 Try this — week of {monday.day} {monday:%b} {monday.year}",
            "cards": cards, "backlog_ids": [q["id"] for q in from_backlog],
            "backlog_left": len(waiting) - len(from_backlog)}


def to_markdown(w: dict) -> str:
    L = [f"# {w['title']}", "",
         f"_{len(w['cards'])} things worth a look, ranked by what you've liked and how small the "
         "first step is. Tick one box per card; the weekly interests review learns from them._", ""]
    for n, c in enumerate(w["cards"], 1):
        flag = " ⚠️ The source contained text aimed at AI agents; the reader ignored it." if c.get("flags") else ""
        L += [f"### {n}. {_esc(c['title'])}", "",
              f"**{KIND_LABEL[c['kind']]} · {c['effort']}** · fits {_esc(', '.join(c['fits']))} · "
              f"from {_esc(c.get('from', ''))} · [{_esc(c.get('source_name') or 'Source')}]({_href(c['url'])}){flag}", "",
              f"{_esc(c['what'])}", "",
              f"**Why you:** {_esc(c['why_you'])}", "",
              f"**First step:** {_esc(c['next_step'])}", "",
              f"- [ ] ✅ Done <!-- card:{c['id']} -->",
              f"- [ ] ⏳ Later <!-- card:{c['id']} -->",
              f"- [ ] 🙅 Not for me <!-- card:{c['id']} -->", ""]
    if w.get("backlog_left"):
        L += [f"<sub>{w['backlog_left']} more from your bookmarks are queued for later weeks.</sub>", ""]
    return "\n".join(L)


def harvest(gh, repo: Path, today: str) -> list[dict]:
    path = Path(repo) / "state/feedback.jsonl"
    done = {ln.get("issue") for ln in load_lines(path) if ln.get("kind") in ("tried", "later", "not_for_me", "weekly-harvested")}
    lines = []
    this_week = week_id(date.fromisoformat(today))
    for issue in gh.list_issues(LABEL, "open"):
        m = MARKER_RE.search(issue.get("body") or "")
        if not m or m.group(1) >= this_week or issue["number"] in done:
            continue
        for kind, cid in parse_ticks(issue.get("body") or ""):
            lines.append({"digest": m.group(1), "issue": issue["number"], "harvested": today,
                          "kind": kind, "id": cid})
        lines.append({"digest": m.group(1), "issue": issue["number"], "harvested": today,
                      "kind": "weekly-harvested"})
    append_lines(path, lines)
    return lines


def prepare(gh, repo: Path, today: str) -> dict:
    """Monday step: harvest, then write reviews/<week>.* and update the queue. Idempotent."""
    repo = Path(repo)
    if date.fromisoformat(today).weekday() != 0:
        return {"skipped": "not Monday"}
    harvested = harvest(gh, repo, today)
    wid = week_id(date.fromisoformat(today))
    if (repo / f"reviews/{wid}.json").exists():
        return {"week": wid, "harvested": len(harvested), "built": False}
    w = build(repo, today)
    if not w:
        return {"week": wid, "harvested": len(harvested), "built": False, "reason": "no cards"}
    write_json(repo / f"reviews/{wid}.json", w)
    (repo / f"reviews/{wid}.md").write_text(to_markdown(w), encoding="utf-8")
    queue_path = repo / "backlog/queue.json"
    if w["backlog_ids"] and queue_path.exists():
        queue = json.loads(queue_path.read_text())
        for q in queue:
            if q["id"] in w["backlog_ids"]:
                q["status"], q["shown"] = "shown", wid
        write_json(queue_path, queue)
    return {"week": wid, "harvested": len(harvested), "built": True, "cards": len(w["cards"])}


def publish(gh, repo: Path, today: str) -> dict:
    repo = Path(repo)
    wid = week_id(date.fromisoformat(today))
    p = repo / f"reviews/{wid}.md"
    if not p.exists():
        return {"created": None, "closed": []}
    gh.ensure_label(LABEL, "a2eeef", "Weekly: things worth trying")
    created = None
    if not any(MARKER_RE.search(i.get("body") or "") and MARKER_RE.search(i["body"]).group(1) == wid
               for i in gh.list_issues(LABEL, "all")):
        w = json.loads((repo / f"reviews/{wid}.json").read_text())
        created = gh.create_issue(w["title"], p.read_text() + f"\n<!-- try-this:{wid} -->\n", [LABEL])["number"]
    closed = []
    for issue in gh.list_issues(LABEL, "open"):
        m = MARKER_RE.search(issue.get("body") or "")
        if m and m.group(1) < wid:
            gh.close_issue(issue["number"])
            closed.append(issue["number"])
    return {"created": created, "closed": closed}
