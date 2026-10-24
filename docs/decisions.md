# Decisions index

One short line per **live** decision, so every session sees the settled surface cheaply and does
not re-litigate it. **This index is auto-loaded every session**, so every byte is paid by every
conversation. The *why*, the rejected alternatives and every past decision live in the per-theme
detail files under `docs/decisions/` named in each heading. **Before reopening or contradicting a
decision, read its detail entry**: `rg -A2 '^## 20'` on the theme file lists every entry with its
status; read that entry only, not the file.

**What earns an entry:** a choice a future session could plausibly reopen: direction,
architecture, contracts, security and privacy posture, licensing, or an alternative that was tried
and rejected. **Not an entry:** experiment results, details settled inside an approved plan, and
anything the code already shows.

**Format and budget** (checked by `.claude/workflow/check.py`):
- `- YYYY-MM-DD — <decision>`, newest first under its theme, at most 250 characters (aim for about
  150).
- Each detail entry opens with `**Status:**` `live, indexed`, `live, not indexed`, `superseded by
  <date>`, `withdrawn` or `record` (results only). Update it when its line goes. An entry covered
  by a line of another date says `live, indexed — under the <date> line`.
- Add the full entry (context, decision, rejected alternatives) to the matching
  `docs/decisions/<theme>.md` as `## YYYY-MM-DD — <decision>`, newest first, `---` between
  entries. Start a new theme file only if none fits, and add its section here.
- The whole index stays under 20 KB. Near it, prune lines first.

---

## Process & tooling · `docs/decisions/process.md`

- 2026-10-23 — Adopted the workflow kit: decisions record, review gates and the workflow check

## Architecture & delivery · `docs/decisions/architecture.md`

- 2026-10-23 — Claude writes picks JSON only; a deterministic renderer adds every link and enforces the format
- 2026-10-23 — Delivery by a GitHub Action as github-actions[bot]; runs push claude/digest-* branches, never main
