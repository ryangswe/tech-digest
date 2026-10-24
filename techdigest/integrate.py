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
    fork = _git(repo, "merge-base", base, ref).strip()
    present = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{fork}:digest/{day}.json"],
                             capture_output=True).returncode == 0
    if present:
        raise IntegrateError(f"a digest for {day} was already delivered before this branch was cut; "
                             "a second run the same day would lose its items, so it is refused")
    paths = {p for _, p in changes}
    for need in (f"digest/{day}.md", f"digest/{day}.json"):
        if need not in paths:
            raise IntegrateError(f"branch has no new {need}")
    replaced = [p for st, p in changes if p.startswith("digest/") and st != "A"]
    if replaced:
        raise IntegrateError(f"a digest for {day} was already delivered; refusing to replace it "
                             f"({', '.join(replaced)})")
    newest = max((p.stem for p in (repo / "digest").glob("*.json")), default="")
    if newest > day:
        raise IntegrateError(f"stale branch: main already has the {newest} digest, newer than {day}")

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
        elif path == "state/weekly.json" and target.exists():
            ours = json.loads(target.read_text(encoding="utf-8")).get("last_proposal") or ""
            theirs = json.loads(text).get("last_proposal") or ""
            write_json(target, {"last_proposal": max(ours, theirs) or None})
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    digest = json.loads((repo / f"digest/{day}.json").read_text(encoding="utf-8"))
    errs = validate_digest(digest)
    if digest.get("date") != day:
        errs.append(f"digest date {digest.get('date')!r} does not match the branch's {day}")
    if errs:
        raise IntegrateError("digest failed validation: " + "; ".join(errs))
    # The JSON is the record; the Markdown (the issue body) is always re-rendered from it here,
    # so a hand-edited .md cannot reach the owner and renderer changes on main cannot break delivery.
    (repo / f"digest/{day}.md").write_text(to_markdown(digest), encoding="utf-8")
    return {"date": day, "paths": sorted(paths)}
