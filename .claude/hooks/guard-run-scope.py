#!/usr/bin/env python3
"""PreToolUse guard for Edit/Write/NotebookEdit: on run branches, only the run's own folders.

Scheduled runs and the bookmark triage work on dedicated branches, and their subagents
(`reader`, `triage`) read text written by strangers. Their only tools are Read and Write, so
this hook is what stops an injected Write from replacing repository code, hooks or settings
(which would then run with the session's shell and network):

    claude/digest-*     build/**
    claude/interests-*  build/**, interests.md, profile.md
    claude/backlog-*    build/**, backlog/triage/**, backlog/out/**

Any other branch (normal development) is not restricted here. On a run branch this guard fails
CLOSED: if it cannot decide, the write is blocked. Shell writes don't pass through it; the
subagents have no shell, and the main session's commands are the repository's own.
"""

import json
import os
import subprocess
import sys

SCOPES = {
    "claude/digest-": ("build/",),
    "claude/interests-": ("build/", "interests.md", "profile.md"),
    "claude/backlog-": ("build/", "backlog/triage/", "backlog/out/"),
}


def repo_root() -> str:
    return os.path.realpath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def branch_of(repo: str) -> str:
    return subprocess.run(["git", "-C", repo, "branch", "--show-current"], capture_output=True,
                          text=True, timeout=10).stdout.strip()


def decide(file_path: str, repo: str, branch: str) -> str | None:
    """None to allow, or the reason to block."""
    scope = next((v for k, v in SCOPES.items() if branch.startswith(k)), None)
    if scope is None:
        return None
    real = os.path.realpath(file_path)
    if not real.startswith(repo + os.sep):
        return f"outside the repository ({file_path})"
    rel = os.path.relpath(real, repo).replace(os.sep, "/")
    for allowed in scope:
        if (allowed.endswith("/") and rel.startswith(allowed)) or rel == allowed:
            return None
    return f"{rel} is outside this run's scope ({', '.join(scope)})"


def main() -> int:
    branch = ""
    try:
        data = json.load(sys.stdin)
        tool_input = data.get("tool_input") or {}
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        repo = repo_root()
        branch = branch_of(repo)
        if not file_path:
            return 0
        reason = decide(file_path, repo, branch)
    except Exception as e:  # on a run branch, a guard that can't decide must block
        if not branch or any(branch.startswith(k) for k in SCOPES):
            print(f"BLOCKED by guard-run-scope: could not check this write ({e}).", file=sys.stderr)
            return 2
        return 0
    if reason:
        print(f"BLOCKED on run branch '{branch}': {reason}. Run sessions and their subagents may "
              "only write their own output files.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
