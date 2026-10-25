"""Load and validate sources.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

TYPES = {"feed", "hn", "arxiv", "html_links", "page_watch", "changelog_md", "npm"}
UNDATED = {"html_links", "changelog_md"}  # bootstrapped on first sight
FLAVORS = {None, "reddit"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ConfigError(ValueError):
    pass


@dataclass
class Source:
    id: str
    name: str
    type: str
    url: str
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    cap: int = 5
    max_age_days: float | None = None
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    aggregator: bool = False
    flavor: str | None = None
    summary_chars: int | None = None
    pattern: str | None = None          # html_links: regex on the link's path
    exclude_paths: list[str] = field(default_factory=list)
    min_title_chars: int = 8
    link_template: str | None = None    # changelog_md / npm: "https://…/tag/v{version}"
    title_prefix: str = ""              # changelog_md / npm: "Claude Code " -> "Claude Code 2.1.310"
    note: str = ""

    @property
    def is_tool(self) -> bool:
        return "tool" in self.tags


@dataclass
class Config:
    timezone: str
    user_agent: str
    max_candidates: int
    summary_chars: int
    default_max_age_days: float
    request_timeout: float
    sources: list[Source]
    dry_run_keywords: list[dict]

    def enabled_sources(self) -> list[Source]:
        return [s for s in self.sources if s.enabled]

    def source(self, source_id: str) -> Source | None:
        return next((s for s in self.sources if s.id == source_id), None)


def _fail(where: str, msg: str) -> None:
    raise ConfigError(f"sources.json: {where}: {msg}")


def parse_config(data: dict) -> Config:
    if not isinstance(data, dict):
        _fail("top level", "must be an object")
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        _fail("sources", "must be a non-empty list")
    known = set(Source.__dataclass_fields__)
    sources: list[Source] = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(raw_sources):
        where = f"source #{i + 1}"
        if not isinstance(raw, dict):
            _fail(where, "must be an object")
        sid = raw.get("id", "")
        if not isinstance(sid, str) or not ID_RE.match(sid):
            _fail(where, f"`id` must be lower-case letters, digits and dashes, got {sid!r}")
        where = f"source `{sid}`"
        if sid in seen_ids:
            _fail(where, "duplicate id")
        seen_ids.add(sid)
        unknown = set(raw) - known
        if unknown:
            _fail(where, f"unknown field(s): {', '.join(sorted(unknown))}")
        for req in ("name", "type", "url"):
            if req not in raw:
                _fail(where, f"missing `{req}`")
        src = Source(**raw)
        if src.type not in TYPES:
            _fail(where, f"`type` must be one of {sorted(TYPES)}, got {src.type!r}")
        if src.flavor not in FLAVORS:
            _fail(where, f"unknown `flavor` {src.flavor!r}")
        if src.enabled and not re.match(r"^https?://", src.url):
            _fail(where, f"enabled source needs an http(s) `url`, got {src.url!r}")
        if src.type == "html_links":
            if not src.pattern:
                _fail(where, "html_links needs a `pattern`")
            try:
                re.compile(src.pattern)
            except re.error as e:
                _fail(where, f"bad `pattern`: {e}")
        if src.type in ("changelog_md", "npm") and src.link_template and "{version}" not in src.link_template:
            _fail(where, "`link_template` must contain {version}")
        if not isinstance(src.cap, int) or src.cap < 0:
            _fail(where, "`cap` must be a non-negative integer")
        for listf in ("tags", "include", "exclude", "exclude_paths"):
            if not isinstance(getattr(src, listf), list):
                _fail(where, f"`{listf}` must be a list")
        sources.append(src)
    return Config(
        timezone=data.get("timezone", "UTC"),
        user_agent=data.get("user_agent", "tech-digest/1.0"),
        max_candidates=int(data.get("max_candidates", 150)),
        summary_chars=int(data.get("summary_chars", 300)),
        default_max_age_days=float(data.get("default_max_age_days", 2)),
        request_timeout=float(data.get("request_timeout", 20)),
        sources=sources,
        dry_run_keywords=list(data.get("dry_run_keywords", [])),
    )


def load_config(path: str | Path = "sources.json") -> Config:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{path}: not found")
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: invalid JSON at line {e.lineno}: {e.msg}")
    return parse_config(data)
