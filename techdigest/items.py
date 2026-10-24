"""The normalised item every parser produces."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from .text import iso
from .urls import canonical_key


@dataclass
class Item:
    source: str
    title: str
    url: str
    summary: str = ""
    published: datetime | None = None
    key: str = ""                       # dedupe key; defaults to the canonical URL
    discussions: list[dict] = field(default_factory=list)  # {name, url, points?, comments?}
    points: int | None = None           # best engagement signal (HN points), if any

    def __post_init__(self) -> None:
        if not self.key:
            self.key = canonical_key(self.url)

    @property
    def id(self) -> str:
        return hashlib.sha1(self.key.encode()).hexdigest()[:10]

    def all_keys(self) -> list[str]:
        """Every key that means "already seen": the item's own and its discussions'."""
        keys = [self.key] + [canonical_key(d["url"]) for d in self.discussions if d.get("url")]
        return list(dict.fromkeys(k for k in keys if k))

    def to_candidate(self, source_name: str, tags: list[str], link_name: str = "") -> dict:
        out = {
            "id": self.id,
            "source": self.source,
            "source_name": source_name,
            "link_name": link_name or source_name,
            "tags": tags,
            "title": self.title,
            "url": self.url,
            "summary": self.summary,
            "published": iso(self.published),
            "keys": self.all_keys(),
        }
        if self.discussions:
            out["discussions"] = self.discussions
        if self.points is not None:
            out["points"] = self.points
        return out
