"""Action cards: written by the quarantined `reader` subagent, one JSON file per item.

    build/cards/<id>.json  ->  `cards validate`  ->  build/cards.json (valid cards, enriched with
    the item's title, link and source from fetched data)

    {
      "id": "<item id>",
      "kind": "try | adopt | watch | read-later",
      "what": "≤ 60 words: what the source says it is or does",
      "why_you": "≤ 60 words: why it matters to this owner (profile.md, interests.md)",
      "next_step": "≤ 40 words: one concrete first step, plain prose, no commands",
      "effort": "15m | 1h | half-day | project",
      "fits": ["names from profile.md's ## Projects"],   # 1 to 3
      "confidence": "high | medium | low",
      "flags": ["instruction-like text noticed in the source, described, not quoted"]  # optional
    }

The same plain-text rules as picks apply (no URLs, HTML, line breaks or Markdown), and
`next_step` may not contain shell commands: a page can't plant `curl … | sh` in the owner's inbox.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .picks import text_errors
from .text import word_count

KINDS = ("try", "adopt", "watch", "read-later")
EFFORTS = ("15m", "1h", "half-day", "project")
CONFIDENCE = ("high", "medium", "low")
WORDS = {"what": 60, "why_you": 60, "next_step": 40}
FIELDS = ("id", "kind", "what", "why_you", "next_step", "effort", "fits", "confidence", "flags")
COMMAND_RE = re.compile(
    r"`|\$\(|\|\s*(?:sh|bash|zsh|python3?)\b|&&|(?:^|\s)(?:curl|wget|sudo|chmod|chown|rm|eval|exec|"
    r"npx|pip3?\s+install|npm\s+(?:i|install)|brew\s+install|git\s+(?:push|clone|config))\b", re.I)


def load_projects(profile_path: Path) -> list[str]:
    """Names under `## Projects` in profile.md, from lines `- Name: description`."""
    text = Path(profile_path).read_text(encoding="utf-8")
    m = re.search(r"^## Projects\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return []
    return [n.strip() for n in re.findall(r"^- ([^:\n]+):", m.group(1), re.M)]


def validate_card(card, known_ids: set[str], projects: list[str]) -> list[str]:
    if not isinstance(card, dict):
        return ["card: must be a JSON object"]
    where = f"card {card.get('id', '?')}"
    errs = []
    extra = set(card) - set(FIELDS)
    if extra:
        errs.append(f"{where}: unknown field(s) {sorted(extra)}; allowed: {list(FIELDS)}")
    if card.get("id") not in known_ids:
        errs.append(f"{where}: id is not one of the items given to the reader")
    for f, allowed in (("kind", KINDS), ("effort", EFFORTS), ("confidence", CONFIDENCE)):
        if card.get(f) not in allowed:
            errs.append(f"{where}.{f}: must be one of {list(allowed)}, got {card.get(f)!r}")
    for f, limit in WORDS.items():
        errs += [e.replace("picks", where, 1) for e in text_errors(where, f, card.get(f))]
        if isinstance(card.get(f), str) and word_count(card[f]) > limit:
            errs.append(f"{where}.{f}: {word_count(card[f])} words, over the {limit}-word limit")
    if isinstance(card.get("next_step"), str) and COMMAND_RE.search(card["next_step"]):
        errs.append(f"{where}.next_step: describe the step in prose; no shell commands or code")
    fits = card.get("fits")
    if not isinstance(fits, list) or not 1 <= len(fits) <= 3:
        errs.append(f"{where}.fits: a list of 1 to 3 project names")
    else:
        bad = [f for f in fits if f not in projects]
        if bad:
            errs.append(f"{where}.fits: {bad} not in profile.md's projects: {projects}")
    flags = card.get("flags", [])
    if not isinstance(flags, list) or len(flags) > 3 or not all(
            isinstance(x, str) and word_count(x) <= 30 for x in flags):
        errs.append(f"{where}.flags: at most 3 short strings")
    return errs


def validate_dir(cards_dir: Path, items: dict[str, dict], projects: list[str]) -> tuple[list[dict], dict[str, list[str]]]:
    """Validate every <id>.json in cards_dir. Returns (valid cards enriched with item fields,
    {id: errors} for the rest). `items` maps id -> {title, url, source_name, ...} from data."""
    valid, errors = [], {}
    for path in sorted(Path(cards_dir).glob("*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors[path.stem] = [f"{path.name}: invalid JSON at line {e.lineno}: {e.msg}"]
            continue
        if isinstance(card, dict) and card.get("id") != path.stem:
            errors[path.stem] = [f"{path.name}: `id` must equal the file name ({path.stem})"]
            continue
        errs = validate_card(card, set(items), projects)
        if errs:
            errors[path.stem] = errs
            continue
        it = items[card["id"]]
        valid.append({**{f: card[f] for f in FIELDS if f in card}, "flags": card.get("flags", []),
                      "title": it["title"], "url": it["url"],
                      "source_name": it.get("link_name") or it.get("source_name", ""),
                      "source": it.get("source", "")})
    return valid, errors


def validate_cards_structure(cards: list[dict]) -> list[str]:
    """Check stored cards on their own (no profile needed), for the delivery workflow."""
    errs = []
    for c in cards:
        where = f"card {c.get('id', '?')}"
        for f, allowed in (("kind", KINDS), ("effort", EFFORTS), ("confidence", CONFIDENCE)):
            if c.get(f) not in allowed:
                errs.append(f"{where}.{f} invalid")
        for f in WORDS:
            errs += text_errors(where, f, c.get(f))
        if isinstance(c.get("next_step"), str) and COMMAND_RE.search(c["next_step"]):
            errs.append(f"{where}.next_step contains a command")
        if not re.match(r"^https?://", str(c.get("url", ""))):
            errs.append(f"{where}: url must be http(s)")
    return errs
