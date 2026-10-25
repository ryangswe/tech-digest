"""One-off triage of the owner's X bookmark backlog. Runs locally, on the Mac with the archive.

    backlog import <archive.zip | folder>   -> backlog/raw/items.json   (gitignored: raw text)
    backlog read                            -> backlog/raw/reads/       (linked pages, untrusted)
    backlog batches [--size 40]             -> backlog/raw/batches/batch-NNN.json (id lists)
      (triage subagents, tools Read+Write)  -> backlog/triage/batch-NNN.json
    backlog validate                        -> errors per batch file
    backlog report                          -> backlog/out/summary.md, backlog/out/queue.json

Raw bookmark text and page text never leave `backlog/raw/` (gitignored). Where the report and
the queue are committed is the owner's decision: the repository is public.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from .cards import load_projects, validate_card
from .picks import text_errors
from .text import parse_date, word_count
from .urls import canonical_key, clean_url

TOPICS = ("agentic coding", "models and pricing", "browser extensions", "on-device ML",
          "TCG tooling", "indie and business", "other")
VERDICTS = ("skip", "note", "try", "deep-dive")
X_HOSTS = ("x.com", "twitter.com", "mobile.twitter.com", "t.co")


class BacklogError(RuntimeError):
    pass


# --- Import ---------------------------------------------------------------------------------

def _js_payload(text: str):
    """`window.YTD.bookmark.part0 = [ ... ]` -> the JSON value."""
    i = text.find("=")
    if not text.lstrip().startswith("window.") or i < 0:
        return json.loads(text)
    return json.loads(text[i + 1:].strip().rstrip(";"))


def _archive_files(path: Path) -> dict[str, str]:
    """{name: text} for the archive's data files, from a .zip or an unzipped folder."""
    path = Path(path)
    out = {}
    if path.is_file() and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if re.search(r"(^|/)data/[^/]+\.(js|json)$", n):
                    out[n] = z.read(n).decode("utf-8", "replace")
    elif path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.suffix in (".js", ".json") and p.is_file():
                out[str(p.relative_to(path))] = p.read_text(encoding="utf-8", errors="replace")
    else:
        raise BacklogError(f"{path}: not a zip file or folder")
    return out


def _unwrap(obj):
    """Archive entries are wrapped: {"bookmark": {...}} or {"tweet": {...}}."""
    if isinstance(obj, dict) and len(obj) == 1:
        (only,) = obj.values()
        if isinstance(only, dict):
            return only
    return obj


def _urls(obj: dict) -> list[str]:
    urls = []
    for key in ("entities", "extended_entities"):
        for u in (obj.get(key) or {}).get("urls", []) or []:
            v = u.get("unwound_url") or u.get("expanded_url") or u.get("expandedUrl") or u.get("url")
            if v:
                urls.append(v)
    for k in ("expandedUrl", "expanded_url"):
        if obj.get(k):
            urls.append(obj[k])
    if not urls and (obj.get("fullText") or obj.get("full_text") or obj.get("text")):
        urls += re.findall(r"https?://\S+", obj.get("fullText") or obj.get("full_text") or obj.get("text"))
    return list(dict.fromkeys(urls))


def _norm(obj: dict, authors: dict[str, str]) -> dict | None:
    obj = _unwrap(obj)
    if not isinstance(obj, dict):
        return None
    tid = str(obj.get("tweetId") or obj.get("tweet_id") or obj.get("id_str") or obj.get("id") or "")
    if not tid.isdigit():
        return None
    text = obj.get("fullText") or obj.get("full_text") or obj.get("text") or ""
    author = (obj.get("user") or {}).get("screen_name") or authors.get(str(obj.get("author_id", ""))) or ""
    created = parse_date(obj.get("createdAt") or obj.get("created_at"))
    return {"tweet_id": tid, "text": text.strip(), "author": author,
            "created": created.date().isoformat() if created else None, "urls": _urls(obj)}


def parse_archive(path: Path) -> tuple[list[dict], dict]:
    """Bookmarks from an X archive (zip or folder) or a folder of X API bookmark pages."""
    files = _archive_files(path)
    found, notes = [], {"files": []}
    for name, text in files.items():
        base = name.rsplit("/", 1)[-1].lower()
        try:
            data = _js_payload(text)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("data"), list):  # an X API page
            users = {u["id"]: u.get("username", "") for u in (data.get("includes") or {}).get("users", [])}
            rows = [_norm(o, users) for o in data["data"]]
        elif "bookmark" in base and isinstance(data, list):
            rows = [_norm(o, {}) for o in data]
        else:
            continue
        rows = [r for r in rows if r]
        if rows:
            notes["files"].append(f"{name}: {len(rows)}")
            found += rows
    if not found:
        names = ", ".join(sorted(n.rsplit('/', 1)[-1] for n in files)[:40])
        raise BacklogError("no bookmarks found. Data files seen: " + (names or "none"))
    return found, notes


def _item_id(tweet_id: str) -> str:
    return hashlib.sha1(f"x:{tweet_id}".encode()).hexdigest()[:10]


def _primary_link(urls: list[str]) -> str | None:
    for u in urls:
        host = (urlsplit(u).hostname or "").lower().removeprefix("www.")
        if host and host not in X_HOSTS:
            return clean_url(u)
    return None


def normalise(rows: list[dict]) -> tuple[dict[str, dict], dict]:
    """Dedupe (same post, or same linked page) into {id: item}; plus counts for the summary."""
    items: dict[str, dict] = {}
    by_link: dict[str, str] = {}
    dupes = 0
    for r in rows:
        iid = _item_id(r["tweet_id"])
        if iid in items:
            dupes += 1
            continue
        link = _primary_link(r["urls"])
        key = canonical_key(link) if link else None
        if key and key in by_link:  # several bookmarks of the same article: one item
            items[by_link[key]]["also"].append(r["tweet_id"])
            dupes += 1
            continue
        post_url = f"https://x.com/{r['author'] or 'i/web'}/status/{r['tweet_id']}"
        text = re.sub(r"\s*https://t\.co/\S+", "", r["text"]).strip()
        items[iid] = {
            "id": iid, "tweet_id": r["tweet_id"], "also": [], "author": r["author"],
            "created": r["created"], "text": r["text"], "post_url": post_url,
            "url": link or post_url, "source": "x-bookmark",
            "source_name": f"@{r['author']}" if r["author"] else "X bookmark",
            "link_name": urlsplit(link).hostname.removeprefix("www.") if link else "X",
            "title": (text[:90] + "…") if len(text) > 90 else (text or "(no text)"),
            "summary": text,
        }
        if key:
            by_link[key] = iid
    vals = list(items.values())
    hosts = Counter(urlsplit(i["url"]).hostname.removeprefix("www.") for i in vals if i["url"] != i["post_url"])
    dates = sorted(i["created"] for i in vals if i["created"])
    stats = {"bookmarks": len(rows), "items": len(vals), "merged_duplicates": dupes,
             "with_text": sum(1 for i in vals if i["text"]), "ids_only": sum(1 for i in vals if not i["text"]),
             "with_link": sum(1 for i in vals if i["url"] != i["post_url"]),
             "top_link_hosts": hosts.most_common(12),
             "date_range": [dates[0], dates[-1]] if dates else None}
    return items, stats


def import_archive(path: Path, root: Path = Path("backlog")) -> dict:
    rows, notes = parse_archive(path)
    items, stats = normalise(rows)
    raw = Path(root) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "items.json").write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    stats["files"] = notes["files"]
    if stats["items"] and stats["ids_only"] > 0.5 * stats["items"]:
        stats["warning"] = ("most bookmarks have no text (the archive holds only ids): triage would "
                            "have nothing to read. Stop and choose a fallback (X API lookup) first.")
    return stats


def make_batches(root: Path = Path("backlog"), size: int = 40) -> list[Path]:
    raw = Path(root) / "raw"
    items = json.loads((raw / "items.json").read_text(encoding="utf-8"))
    ids = sorted(items, key=lambda i: (items[i]["created"] or "", i), reverse=True)  # newest first
    out = raw / "batches"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("batch-*.json"):
        old.unlink()
    paths = []
    for n in range(0, len(ids), size):
        p = out / f"batch-{n // size + 1:03d}.json"
        p.write_text(json.dumps(ids[n:n + size]) + "\n")
        paths.append(p)
    return paths


# --- Triage output --------------------------------------------------------------------------

def validate_triage(path: Path, batch_ids: list[str], projects: list[str]) -> list[str]:
    """Errors in one backlog/triage/batch-NNN.json. Every batch id needs exactly one verdict."""
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return [f"{Path(path).name}: {e}"]
    if not isinstance(rows, list):
        return [f"{Path(path).name}: must be a JSON list"]
    errs = []
    seen = set()
    for r in rows:
        if not isinstance(r, dict):
            errs.append("each entry must be an object")
            continue
        rid = r.get("id")
        where = f"{rid}"
        if rid not in batch_ids:
            errs.append(f"{where}: not in this batch")
        if rid in seen:
            errs.append(f"{where}: appears twice")
        seen.add(rid)
        if r.get("verdict") not in VERDICTS:
            errs.append(f"{where}.verdict: one of {list(VERDICTS)}")
        if r.get("topic") not in TOPICS:
            errs.append(f"{where}.topic: one of {list(TOPICS)}")
        errs += text_errors(where, "reason", r.get("reason"))
        if isinstance(r.get("reason"), str) and word_count(r["reason"]) > 25:
            errs.append(f"{where}.reason: at most 25 words")
        sub = r.get("subtopic", "")
        if sub and (not isinstance(sub, str) or word_count(sub) > 5):
            errs.append(f"{where}.subtopic: at most 5 words")
        if r.get("verdict") in ("try", "deep-dive"):
            card = r.get("card")
            if not isinstance(card, dict):
                errs.append(f"{where}.card: required for try and deep-dive")
            else:
                errs += validate_card({"id": rid, **{k: v for k, v in card.items() if k != "id"}},
                                      set(batch_ids), projects)
        extra = set(r) - {"id", "verdict", "topic", "subtopic", "reason", "card"}
        if extra:
            errs.append(f"{where}: unknown field(s) {sorted(extra)}")
    missing = [i for i in batch_ids if i not in seen]
    if missing:
        errs.append(f"no verdict for {len(missing)} id(s): {', '.join(missing[:10])}")
    return errs


def validate_all(root: Path = Path("backlog"), profile: Path = Path("profile.md")) -> dict[str, list[str]]:
    root = Path(root)
    projects = load_projects(profile)
    report = {}
    for b in sorted((root / "raw/batches").glob("batch-*.json")):
        ids = json.loads(b.read_text())
        t = root / "triage" / b.name
        report[b.name] = validate_triage(t, ids, projects) if t.exists() else ["not triaged yet"]
    return report


def build_report(root: Path = Path("backlog")) -> tuple[str, list[dict]]:
    """(summary Markdown, ranked queue of try/deep-dive cards) from validated triage files."""
    root = Path(root)
    items = json.loads((root / "raw/items.json").read_text(encoding="utf-8"))
    rows = []
    for t in sorted((root / "triage").glob("batch-*.json")):
        rows += json.loads(t.read_text(encoding="utf-8"))
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_topic[r["topic"]].append(r)
    verdicts = Counter(r["verdict"] for r in rows)
    L = ["# What's in my bookmarks", "",
         f"{len(rows)} bookmarks triaged: " + ", ".join(f"{verdicts[v]} {v}" for v in VERDICTS) + ".", "",
         "<!-- SYNTHESIS: the lead session writes a short overview here from the sections below. -->", ""]
    from .render import _esc
    for topic in sorted(by_topic, key=lambda t: -len(by_topic[t])):
        rs = by_topic[topic]
        c = Counter(r["verdict"] for r in rs)
        L += [f"## {topic.capitalize()} ({len(rs)})", "",
              f"{c['deep-dive']} deep-dive, {c['try']} try, {c['note']} note, {c['skip']} skip.", ""]
        subs = Counter(r.get("subtopic") for r in rs if r.get("subtopic"))
        if subs:
            L += ["Recurring: " + ", ".join(f"{s} ({n})" for s, n in subs.most_common(6)) + ".", ""]
        for r in sorted(rs, key=lambda r: VERDICTS.index(r["verdict"]), reverse=True):
            if r["verdict"] == "skip":
                continue
            it = items[r["id"]]
            L.append(f"- **{r['verdict']}** · {_esc(r['reason'])} ([{_esc(it['link_name'])}]({it['url']}) · "
                     f"[post]({it['post_url']}))")
        L.append("")
    queue = []
    for r in rows:
        if r["verdict"] in ("try", "deep-dive"):
            it = items[r["id"]]
            card = {k: v for k, v in r["card"].items() if k not in ("id", "flags")}
            host = it["link_name"]
            queue.append({"id": r["id"], **card, "flagged": bool(r["card"].get("flags")),
                          # a title from validated card text, never the raw post text
                          "title": (" ".join(card["what"].split()[:12]) + "…") if host == "X" else
                                   f"{host}: " + " ".join(card["what"].split()[:10]) + "…",
                          "url": it["url"],
                          "source_name": it["link_name"], "source": "x-bookmark",
                          "verdict": r["verdict"], "topic": r["topic"], "status": "queued"})
    from .cards import CONFIDENCE, EFFORTS
    queue.sort(key=lambda q: (q["verdict"] != "deep-dive", CONFIDENCE.index(q["confidence"]),
                              EFFORTS.index(q["effort"])))
    return "\n".join(L), queue
