"""Delivery, run by the GitHub Action as github-actions[bot] so the owner gets emailed.

    harvest  read the still-open digest issues' ticks, reactions and owner comments
             into state/feedback.jsonl (before they are closed)
    publish  open today's issue (once), link waiting interests PRs, close earlier digests
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .feedback import append_lines, load_lines, parse_digs, parse_ticks
from .render import digest_title

DIGEST_LABEL = "digest"
FAIL_LABEL = "digest-failure"
MARKER_RE = re.compile(r"<!-- digest:(\d{4}-\d{2}-\d{2}) -->")
BODY_MAX = 65000


def issue_day(issue: dict) -> str | None:
    m = MARKER_RE.search(issue.get("body") or "")
    return m.group(1) if m else None


def _lookup(repo_root: Path, day: str) -> dict:
    try:
        d = json.loads((repo_root / f"digest/{day}.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return {e["id"]: e for s in ("top", "skim", "tools") for e in d.get(s, [])}


def harvest(gh, repo_root: Path, owner: str, today: str) -> list[dict]:
    repo_root = Path(repo_root)
    path = repo_root / "state/feedback.jsonl"
    done = {ln.get("issue") for ln in load_lines(path)}
    lines: list[dict] = []
    for issue in gh.list_issues(DIGEST_LABEL, "open"):
        day = issue_day(issue)
        if not day or day >= today or issue["number"] in done:
            continue
        base = {"digest": day, "issue": issue["number"], "harvested": today}
        items = _lookup(repo_root, day)
        for vote, iid in parse_ticks(issue.get("body") or ""):
            e = items.get(iid, {})
            lines.append({**base, "kind": "vote", "vote": vote, "id": iid,
                          "title": e.get("headline") or e.get("title", ""), "source": e.get("source", "")})
        for iid in parse_digs(issue.get("body") or ""):
            e = items.get(iid, {})
            lines.append({**base, "kind": "dig", "id": iid,
                          "title": e.get("headline") or e.get("title", ""), "source": e.get("source", "")})
        for r in gh.issue_reactions(issue["number"]):
            if r.get("user", {}).get("login") == owner and r.get("content") in ("+1", "-1"):
                lines.append({**base, "kind": "reaction", "vote": 1 if r["content"] == "+1" else -1})
        for c in gh.issue_comments(issue["number"]):
            if c.get("user", {}).get("login") == owner and (c.get("body") or "").strip():
                lines.append({**base, "kind": "comment", "text": c["body"].strip()[:2000]})
        lines.append({**base, "kind": "harvested"})  # marks the issue done even with no signals
    append_lines(path, lines)
    return lines


def dig_requests(issues: list[dict], repo_root: Path) -> list[dict]:
    """Items ticked 🔍 on open digest issues, as read items: [{id, url, title, ...}]."""
    out = []
    for issue in issues:
        day = issue_day(issue)
        items = _lookup(Path(repo_root), day) if day else {}
        for iid in parse_digs(issue.get("body") or ""):
            e = items.get(iid)
            if e:
                out.append({"id": iid, "url": e["url"], "title": e.get("title", ""),
                            "source": e.get("source", ""), "source_name": e.get("source_name", ""),
                            "link_name": e.get("link_name", ""), "summary": e.get("summary", ""),
                            "digest": day})
    return out


def _interests_note(gh) -> str:
    prs = [p for p in gh.open_pulls() if p.get("head", {}).get("ref", "").startswith("claude/interests-")]
    if not prs:
        return ""
    links = ", ".join(f"[#{p['number']} {p['title']}]({p['html_url']})" for p in prs)
    return f"\n> 📝 Proposed `interests.md` changes are waiting for your review: {links}\n"


def publish(gh, repo_root: Path, today: str) -> dict:
    repo_root = Path(repo_root)
    md = (repo_root / f"digest/{today}.md").read_text(encoding="utf-8")
    gh.ensure_label(DIGEST_LABEL, "f9d0c4", "Daily tech digest")
    created = None
    if not any(issue_day(i) == today for i in gh.list_issues(DIGEST_LABEL, "all")):
        marker = f"\n<!-- digest:{today} -->\n"
        note = _interests_note(gh)
        if len(md) + len(note) + len(marker) > BODY_MAX:
            md = md[: BODY_MAX - len(note) - len(marker) - 80] + \
                f"\n\n_(Truncated: the full digest is digest/{today}.md in the repository.)_\n"
        created = gh.create_issue(digest_title(today), md + note + marker, [DIGEST_LABEL])["number"]
    closed = []
    for issue in gh.list_issues(DIGEST_LABEL, "open"):
        day = issue_day(issue)
        if day and day < today:
            gh.close_issue(issue["number"])
            closed.append(issue["number"])
    return {"created": created, "closed": closed}


def report_failure(gh, title: str, body: str) -> int | None:
    """Open a failure issue once per title (re-runs don't pile up duplicates)."""
    gh.ensure_label(FAIL_LABEL, "d73a4a", "A daily digest run failed")
    if any(i["title"] == title for i in gh.list_issues(FAIL_LABEL, "open")):
        return None
    return gh.create_issue(title, body[:BODY_MAX], [FAIL_LABEL])["number"]


def check_delivered(gh, repo_root: Path, today: str) -> int | None:
    if (Path(repo_root) / f"digest/{today}.md").exists():
        return None
    return report_failure(gh, f"No digest today ({today})",
                          "The scheduled run did not deliver a digest by mid-morning. Check the "
                          "task's latest run at claude.ai/code/routines (a green status does not "
                          "prove it pushed), and any `claude/digest-*` branch left on the repo.")
