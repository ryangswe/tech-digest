"""The deterministic fetch step: every source -> new, deduped, capped candidates."""

from __future__ import annotations

import re
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Config, Source
from .items import Item
from .net import FetchError, http_get
from .parse import PARSERS, page_hash, page_paragraphs, paragraph_hashes
from .state import Seen, SourceState, write_json
from .text import iso, local_now, matches_any, truncate


def expand_url(url: str, now: datetime) -> str:
    """`{since:24}` -> the Unix time 24 hours before `now`."""
    return re.sub(r"\{since:(\d+)\}",
                  lambda m: str(int((now - timedelta(hours=int(m.group(1)))).timestamp())), url)


def page_watch(src: Source, raw: bytes, sst: SourceState, now: datetime, today: str) -> list[Item]:
    """One item when the page's text changed since the last run; nothing on first sight."""
    paras = page_paragraphs(raw)
    if not paras:
        raise FetchError("page has no readable text")
    h, hashes = page_hash(paras), paragraph_hashes(paras)
    prev = sst.page(src.id)
    if prev and prev.get("hash") == h:
        prev["checked"] = today
        return []
    sst.set_page(src.id, {"hash": h, "paras": hashes, "changed": today, "checked": today})
    if not prev:
        return []
    old = set(prev.get("paras", []))
    new_set = set(hashes)
    changed = [p for p, ph in zip(paras, hashes) if ph not in old]
    removed = len([ph for ph in prev.get("paras", []) if ph not in new_set])
    since = prev.get("changed", "the last check")
    if len(changed) > 0.5 * len(paras):
        summary = (f"Most of this page's text changed since {since}, which may be a redesign "
                   "rather than a policy change.")
    else:
        parts = [f"Text added or changed since {since}: " + " / ".join(changed)] if changed else []
        if removed:
            parts.append(f"{removed} paragraph(s) removed.")
        summary = " ".join(parts) or f"The page changed since {since}."
    return [Item(src.id, f"{src.name} changed", src.url, summary, now,
                 key=f"page:{src.id}:{h[:12]}")]


def _within_window(item: Item, src: Source, cfg: Config, now: datetime) -> bool:
    if src.type in ("html_links", "page_watch") or item.published is None:
        return True
    days = src.max_age_days if src.max_age_days is not None else cfg.default_max_age_days
    return item.published >= now - timedelta(days=days)


def _keyword_ok(item: Item, src: Source) -> bool:
    text = f"{item.title} {item.summary}"
    if src.include and not matches_any(text, src.include):
        return False
    return not (src.exclude and matches_any(text, src.exclude))


def merge(groups: list[tuple[Source, list[Item]]]) -> list[tuple[Source, Item]]:
    """One entry per key. First-party sources win over aggregators; discussions are combined."""
    ordered = [g for g in groups if not g[0].aggregator] + [g for g in groups if g[0].aggregator]
    out: dict[str, tuple[Source, Item]] = {}
    for src, items in ordered:
        for it in items:
            if it.key not in out:
                out[it.key] = (src, it)
                continue
            kept = out[it.key][1]
            urls = {d["url"] for d in kept.discussions}
            kept.discussions += [d for d in it.discussions if d["url"] not in urls]
            if it.points is not None and (kept.points or 0) < it.points:
                kept.points = it.points
            if not kept.summary and it.summary:
                kept.summary = it.summary
    return list(out.values())


def _link_name(src: Source, item: Item) -> str:
    """An aggregator's item links to someone else's site: name the site, not the aggregator."""
    host = (urlsplit(item.url).hostname or "").lower()
    if src.aggregator and host and not host.endswith(("ycombinator.com", "reddit.com")):
        return host[4:] if host.startswith("www.") else host
    return src.name


def run_fetch(cfg: Config, *, state_dir: Path, out_dir: Path, now: datetime | None = None,
              getter=None, log=print) -> dict:
    now = now or datetime.now(timezone.utc)
    today = local_now(cfg.timezone, now).date().isoformat()
    state_dir, out_dir = Path(state_dir), Path(out_dir)
    seen = Seen.load(state_dir / "seen.json")
    sst = SourceState.load(state_dir / "sources.json")
    if getter is None:
        def getter(url: str, source_id: str) -> bytes:
            return http_get(url, cfg.user_agent, cfg.request_timeout)

    report: dict[str, dict] = {}
    groups: list[tuple[Source, list[Item]]] = []
    log(f"{'source':28} {'ok?':4} {'parsed':>6}  (parsed = items in the feed, before age, keyword and seen filters)")
    for src in cfg.enabled_sources():
        entry = {"name": src.name, "ok": False, "fetched": 0, "new": 0}
        items: list[Item] = []
        try:
            raw = getter(expand_url(src.url, now), src.id)
            if src.type == "page_watch":
                items = page_watch(src, raw, sst, now, today)
                entry["fetched"] = 1
            else:
                items = PARSERS[src.type](raw, src)
                entry["fetched"] = len(items)
            entry["ok"] = True
        except Exception as e:  # one broken source never stops the run
            entry["error"] = str(e)[:120] or type(e).__name__
        sst.record(src.id, entry["ok"], entry["fetched"], today)
        items = [i for i in items if _within_window(i, src, cfg, now) and _keyword_ok(i, src)]
        if src.type == "html_links" and entry["fetched"] and not sst.bootstrapped(src.id):
            for it in items:  # undated listing: today's links are the baseline, not news
                seen.mark(it.all_keys(), today)
            sst.set_bootstrapped(src.id, today)
            entry["bootstrapped"] = True
            items = []
        limit = src.summary_chars or (600 if src.type == "page_watch" else cfg.summary_chars)
        for it in items:
            it.summary = truncate(it.summary, limit)
        groups.append((src, items))
        report[src.id] = entry
        note = entry.get("error", "") or ("baseline recorded (first sight)" if entry.get("bootstrapped") else "")
        log(f"{src.id:28} {'ok ' if entry['ok'] else 'FAIL'} {entry['fetched']:6}  {note}")

    order = {s.id: n for n, s in enumerate(cfg.sources)}
    fresh = [(s, i) for s, i in merge(groups) if not seen.contains_any(i.all_keys())]
    capped: list[tuple[Source, Item]] = []
    for src in cfg.enabled_sources():
        mine = [(s, i) for s, i in fresh if s.id == src.id]
        mine.sort(key=lambda p: (-(p[1].points or 0),
                                 -(p[1].published.timestamp() if p[1].published else 0)))
        capped += mine[:src.cap]
    capped.sort(key=lambda p: (not p[0].is_tool, order[p[0].id]))
    capped = capped[:cfg.max_candidates]
    for s, _ in capped:
        report[s.id]["new"] += 1

    candidates = [i.to_candidate(s.name, s.tags, _link_name(s, i)) for s, i in capped]
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = {"date": today, "generated_at": iso(now), "timezone": cfg.timezone,
           "candidates": candidates}
    write_json(out_dir / "candidates.json", doc)
    full_report = {"date": today, "sources": report, "quiet": sst.quiet(),
                   "candidates": len(candidates)}
    write_json(out_dir / "fetch-report.json", full_report)
    seen.save(state_dir / "seen.json")
    sst.save(state_dir / "sources.json")
    if any(e.get("error") == "TLS certificate error" for e in report.values()):
        log("note: TLS certificate errors on a Mac usually mean Python lacks CA certificates; "
            "see docs/setup.md (SSL_CERT_FILE=/etc/ssl/cert.pem)")
    log(f"{len(candidates)} candidates from {sum(1 for e in report.values() if e['ok'])}"
        f"/{len(report)} sources -> {out_dir / 'candidates.json'}")
    return full_report


def mark_seen(*, state_dir: Path, candidates_path: Path, today: str) -> tuple[int, int]:
    """Mark every candidate (picked or not) as seen, then prune. Returns (added, pruned)."""
    import json
    seen = Seen.load(Path(state_dir) / "seen.json")
    before = len(seen)
    doc = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
    for c in doc["candidates"]:
        seen.mark(c.get("keys") or [], today)
    added = len(seen) - before
    pruned = seen.prune(today)
    seen.save(Path(state_dir) / "seen.json")
    return added, pruned
