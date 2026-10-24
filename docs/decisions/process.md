# Decisions — Process & tooling

Full rationale for this theme's decisions, newest first. The lean, auto-loaded index is
`docs/decisions.md`.

---

## 2026-10-23 — Adopted the workflow kit: decisions record, review gates and the workflow check

**Status:** live, indexed

**Context.** A new repository whose daily runs are unattended cloud sessions; the owner wants
the same branch, review and decision rules in every session, local or scheduled.

**Decision.** The repository uses the workflow kit (github.com/ryangswe/claude-workflow): a
committed `.claude/` with agents, skills and a branch guard, this decisions record, and
`.claude/workflow/check.py` keeping them consistent. The kit's managed files are updated with
`workflow-kit sync`; `CLAUDE.md` and these docs are the repository's own.

**Rejected.** The full level: one milestone and one maintainer do not need the planner,
architect and executor roles. The v1 plan was written from the kit's template by hand.
