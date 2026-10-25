"""Tamper check around a quarantined subagent (`reader`, `triage`).

    python3 -m techdigest scope snapshot      -> prints a token
    (the subagent runs)
    python3 -m techdigest scope check TOKEN   -> exit 0, or 2 naming what changed

The token is a fingerprint of everything the subagent must not touch: tracked files (diff and
status), untracked files, HEAD, and the build files the renderer trusts (candidates, picks, the
item list, 🔍 requests). It lives only in the calling session's context, which the subagent can't
reach, so the subagent can't rewrite the evidence too. Its own output folders are left out.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

PROTECTED_BUILD = ("build/candidates.json", "build/picks.json", "build/reads/items.json",
                   "build/dig.json", "build/fetch-report.json", "build/reads/index.json")
OUTPUT_DIRS = ("build/cards/", "backlog/triage/")


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def _h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def components(repo: Path) -> dict[str, str]:
    repo = Path(repo)
    untracked = [p for p in _git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p]
    untracked = [p for p in untracked if not p.decode().startswith(OUTPUT_DIRS)]
    blob = b"".join(p + b"\0" + (repo / p.decode()).read_bytes() for p in sorted(untracked)
                    if (repo / p.decode()).is_file())
    out = {
        "head": _git(repo, "rev-parse", "HEAD").decode().strip()[:12],
        "tracked": _h(_git(repo, "diff", "HEAD", "--binary")),
        "untracked": _h(blob),
    }
    for rel in PROTECTED_BUILD:
        p = repo / rel
        out[rel] = _h(p.read_bytes()) if p.exists() else "-"
    return out


def snapshot(repo: Path) -> str:
    return ",".join(f"{k}={v}" for k, v in components(repo).items())


def check(repo: Path, token: str) -> list[str]:
    """Names of the components that changed since `token`; empty means untouched."""
    before = dict(part.split("=", 1) for part in token.split(",") if "=" in part)
    now = components(repo)
    return sorted(k for k in set(before) | set(now) if before.get(k) != now.get(k))
