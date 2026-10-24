"""Shared test helpers. Run the suite from the repository root:
python3 -m unittest discover -s tests"""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from techdigest.config import Source

ROOT = Path(__file__).resolve().parent.parent
FEEDS = ROOT / "fixtures/feeds"
NOW = datetime(2026, 10, 23, 11, 30, tzinfo=timezone.utc)


def src(**kw) -> Source:
    base = {"id": "test", "name": "Test", "type": "feed", "url": "https://example.com/feed"}
    base.update(kw)
    return Source(**base)


def feed(name: str) -> bytes:
    return (FEEDS / name).read_bytes()


class TempDir:
    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix="techdigest-test-"))
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)


def candidates_doc(n_tools: int = 2, n_other: int = 12, day: str = "2026-10-23") -> dict:
    cands = []
    for i in range(n_other + n_tools):
        tool = i >= n_other
        cands.append({
            "id": f"{i:010x}", "source": "tools" if tool else "news",
            "source_name": "Tool releases" if tool else "News", "link_name": "News",
            "tags": ["tool"] if tool else [], "title": f"Item {i} title",
            "url": f"https://example.com/{i}", "summary": f"Summary {i}.", "published": None,
            "keys": [f"example.com/{i}"],
        })
    return {"date": day, "candidates": cands}


def good_picks(doc: dict) -> dict:
    ids = [c["id"] for c in doc["candidates"] if "tool" not in c["tags"]]
    tools = [c["id"] for c in doc["candidates"] if "tool" in c["tags"]]
    return {
        "date": doc["date"],
        "opener": "Good morning: three things worth your coffee.",
        "top": [{"id": i, "headline": f"Headline {n}", "summary": "The source says a thing happened.",
                 "why": "It touches the tools you ship with."} for n, i in enumerate(ids[:3], 1)],
        "skim": [{"id": i, "line": "One line on what the source says."} for i in ids[3:8]],
        "tools": [{"id": i, "line": "Version 1.2 adds a flag."} for i in tools],
    }


def dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
