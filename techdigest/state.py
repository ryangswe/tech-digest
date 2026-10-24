"""Committed run state: seen items (state/seen.json) and per-source health (state/sources.json)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

SEEN_DAYS = 60


def _read_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")


class Seen:
    """{key: first-seen date}. Sorted on save so daily diffs stay small."""

    def __init__(self, items: dict[str, str] | None = None):
        self.items: dict[str, str] = dict(items or {})

    @classmethod
    def load(cls, path: Path) -> "Seen":
        data = _read_json(path, {})
        return cls(data.get("items", {}))

    def save(self, path: Path) -> None:
        write_json(path, {"version": 1, "items": self.items})

    def contains(self, key: str) -> bool:
        return key in self.items

    def contains_any(self, keys: list[str]) -> bool:
        return any(k in self.items for k in keys)

    def mark(self, keys: list[str], day: str) -> None:
        for k in keys:
            if k and k not in self.items:
                self.items[k] = day

    def prune(self, today: str, days: int = SEEN_DAYS) -> int:
        """Drop keys first seen more than `days` days ago; they may come back after that."""
        cutoff = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
        old = [k for k, d in self.items.items() if d < cutoff]
        for k in old:
            del self.items[k]
        return len(old)

    def union(self, other: "Seen") -> "Seen":
        merged = dict(self.items)
        for k, d in other.items.items():
            if k not in merged or d < merged[k]:
                merged[k] = d
        return Seen(merged)

    def __len__(self) -> int:
        return len(self.items)


class SourceState:
    """Per-source health and page-watch snapshots: {"sources": {id: {...}}}."""

    def __init__(self, data: dict | None = None):
        self.data = data or {}
        self.data.setdefault("sources", {})

    @classmethod
    def load(cls, path: Path) -> "SourceState":
        return cls(_read_json(path, {}))

    def save(self, path: Path) -> None:
        write_json(path, self.data)

    def get(self, source_id: str) -> dict:
        return self.data["sources"].setdefault(source_id, {})

    def record(self, source_id: str, ok: bool, fetched: int, day: str) -> None:
        s = self.get(source_id)
        if ok:
            s["last_ok"] = day
            s["fail_days"] = 0
            s["empty_days"] = 0 if fetched else s.get("empty_days", 0) + 1
        else:
            s["fail_days"] = s.get("fail_days", 0) + 1

    def bootstrapped(self, source_id: str) -> bool:
        return bool(self.get(source_id).get("bootstrapped"))

    def set_bootstrapped(self, source_id: str, day: str) -> None:
        self.get(source_id)["bootstrapped"] = day

    def page(self, source_id: str) -> dict | None:
        return self.get(source_id).get("page")

    def set_page(self, source_id: str, page: dict) -> None:
        self.get(source_id)["page"] = page

    def quiet(self, days: int = 3) -> list[str]:
        """Sources that parsed zero items `days` runs in a row: their format probably changed."""
        return sorted(sid for sid, s in self.data["sources"].items() if s.get("empty_days", 0) >= days)

    def merged_with(self, newer: "SourceState") -> "SourceState":
        """Per-source union where `newer`'s entries win."""
        out = json.loads(json.dumps(self.data))
        out["sources"].update(json.loads(json.dumps(newer.data["sources"])))
        return SourceState(out)
