"""Bring a `claude/digest-DATE` branch's output into the `main` working tree, and nothing else.

Run by the delivery Action from a checkout of `main`. A scheduled run may only add that day's
digest files and update run state; any other path, or a deletion, refuses the whole branch.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .render import to_markdown, validate_digest
from .state import Seen, SourceState, write_json

BRANCH_RE = re.compile(r"^claude/digest-(\d{4}-\d{2}-\d{2})$")
STATE_FILES = ("state/seen.json", "state/sources.json", "state/weekly.json")


class IntegrateError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode:
        raise IntegrateError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout


def allowed_paths(day: str) -> set[str]:
    return {f"digest/{day}.md", f"digest/{day}.json", *STATE_FILES}


def integrate(repo: Path, branch: str, base: str = "origin/main", remote: str = "origin") -> dict:
    """Copy the branch's allowed files into `repo`'s working tree. Returns what changed."""
    repo = Path(repo)
    m = BRANCH_RE.match(branch)
    if not m:
        raise IntegrateError(f"branch {branch!r} is not claude/digest-YYYY-MM-DD")
    day = m.group(1)
    ref = f"{remote}/{branch}"
    changes = [ln.split("\t") for ln in
               _git(repo, "diff", "--name-status", "--no-renames", f"{base}...{ref}").splitlines() if ln]
    allowed = allowed_paths(day)
    refused = [f"{st} {p}" for st, p in changes if p not in allowed or st not in ("A", "M")]
    if refused:
        raise IntegrateError("branch changes paths a scheduled run may not touch: " + ", ".join(refused))
    paths = {p for _, p in changes}
    for need in (f"digest/{day}.md", f"digest/{day}.json"):
        if need not in paths and not (repo / need).exists():
            raise IntegrateError(f"branch has no {need}")

    def show(path: str) -> str:
        return _git(repo, "show", f"{ref}:{path}")

    for path in sorted(paths):
        text = show(path)
        target = repo / path
        if path == "state/seen.json" and target.exists():
            ours = Seen(json.loads(target.read_text(encoding="utf-8")).get("items", {}))
            merged = ours.union(Seen(json.loads(text).get("items", {})))
            merged.prune(day)
            merged.save(target)
        elif path == "state/sources.json" and target.exists():
            ours = SourceState(json.loads(target.read_text(encoding="utf-8")))
            write_json(target, ours.merged_with(SourceState(json.loads(text))).data)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    digest = json.loads((repo / f"digest/{day}.json").read_text(encoding="utf-8"))
    errs = validate_digest(digest)
    if digest.get("date") != day:
        errs.append(f"digest date {digest.get('date')!r} does not match the branch's {day}")
    md = (repo / f"digest/{day}.md").read_text(encoding="utf-8")
    if md != to_markdown(digest):
        errs.append(f"digest/{day}.md does not match a fresh render of digest/{day}.json")
    if errs:
        raise IntegrateError("digest failed validation: " + "; ".join(errs))
    return {"date": day, "paths": sorted(paths)}
