# Decisions — Architecture & delivery

Full rationale for this theme's decisions, newest first. The lean, auto-loaded index is
`docs/decisions.md`.

---

## 2026-11-23 — X bookmarks come from the owner's own passive capture script, scrolled by hand; no automation of the X session, no third-party userscript, no paid API

**Status:** live, indexed

**Context.** X's data download has no bookmarks, and the X API that returns them is paid (and
returns only the latest 800). The free twitter-web-exporter userscript works, but it is a large
third-party script running in the owner's signed-in session. The owner has two accounts.

**Decision.** `tools/x-bookmarks-capture.js`, short enough to read in full, keeps copies of the
Bookmarks GraphQL responses X's own page receives while the owner scrolls by hand, and saves one
JSON file per account. It sends no requests, loads no code and never scrolls or clicks; a test
checks for those calls and runs the script against a fake browser. No agent drives the owner's X
session, and nothing works around X's rate limits. The instructions say plainly that X's terms
restrict scraping, so whether to use it is the owner's call. `backlog import` reads the files,
tags rows with the account and merges posts across accounts. Raw captures stay out of the
repository like other raw bookmark text.

**Rejected.** Paid exporters and the X API (cost, an API key, the 800 cap); twitter-web-exporter
as the main route (too much third-party code to read; its reader stays for old exports); an
agent scrolling the page through browser automation (drives the owner's session, and would be
automated scraping); an auto-scrolling script (same reason).

---

## 2026-10-24 — Untrusted page and bookmark text is read only by Read/Write-only subagents; their output reaches the owner only through code validation

**Status:** live, indexed

**Context.** v2 reads full web pages and the owner's bookmarked posts, all written by strangers.
The daily session has a shell, Full network access (the owner's choice) and push rights. The
repository is also public, so cards, weekly issues and committed reports are public.

**Decision.** Deterministic code fetches (`read`, `backlog read`) and marks files untrusted. Only
the `reader` and `triage` subagents (`tools: Read, Write`, tested) open them. Their cards and
verdicts are validated by `techdigest/cards.py` and `backlog.py` (no URLs, Markdown, HTML or
shell commands; `fits` from `profile.md`) before anything renders. A card stores only
`flagged: true/false`, shown as a fixed warning. The main session never opens `build/reads/` and
sees only code-made status text. `scope snapshot`/`check` wraps each subagent run, and the run
stops on any change outside the subagent's output folder. A fail-closed write-scope hook for run
branches (`.claude/hooks/guard-run-scope.py`, wired with the owner's approval) is the second
layer. Raw bookmark and page text and per-bookmark verdicts stay in gitignored `backlog/`; the
bookmark report and queue are committed and public (the owner's decision, 2026-10-24).

**Rejected.** The main session using WebFetch or curl (attacker text in the session that holds
the shell); a GitHub Actions reviewer (an OAuth secret and a second runtime); Custom-allowlist
reading only (most cards would rest on titles).

---

## 2026-10-23 — Claude writes picks JSON only; a deterministic renderer adds every link and enforces the format

**Status:** live, indexed

**Context.** The digest must link every item to its source and claim nothing beyond it. If
Claude wrote the Markdown, a link could be invented or a section dropped, and the format could
not be tested.

**Decision.** The judgement step's only output is `build/picks.json` (`techdigest/picks.py`):
candidate ids plus short plain-prose fields. `render` refuses unknown or repeated ids, any URL
or Markdown in the text, the wrong section sizes and more than about 1,100 words, and builds
`digest/DATE.json`. `to_markdown` is a pure function of that JSON, so delivery re-renders and
refuses a Markdown file that does not match. The JSON (`schema_version: 1`) is also the contract
for any downstream consumer such as a video pipeline.

**Rejected.** Claude writing Markdown directly, checked by regex afterwards: weaker guarantees
and harder to test.

---

## 2026-10-23 — Delivery by a GitHub Action as github-actions[bot]; runs push claude/digest-* branches, never main

**Status:** live, indexed

**Context.** Cloud sessions act on GitHub as the owner, and GitHub never emails you about your
own actions, so an issue opened by the session would arrive silently. The cloud proxy also lets a
session push to `main`. The workflow kit's rule is that agents never change the default branch.

**Decision.** The run pushes `claude/digest-DATE`. `.github/workflows/deliver.yml` (push
trigger) copies only `digest/DATE.{md,json}` and `state/{seen,sources,weekly}.json` into `main`
(`techdigest/integrate.py`: anything else, or a deletion, fails the run), merges `seen.json` as a
union, harvests the previous issue's feedback into `state/feedback.jsonl`, commits, opens the
issue as the bot, closes the previous one and deletes the branch. A daily watchdog opens an
issue if no digest landed. Per-item feedback is tick boxes in the issue body, since reactions
attach to whole issues or comments only, and one comment per item would mean about 15 emails a day.

**Trust boundary.** The allowlist guards against an unattended run's mistakes, not a hostile
session: anything with push access could change a workflow file on its branch. Real enforcement
needs branch protection or a ruleset on `main`, which for a private repository needs a paid
GitHub plan. Revisit if the repository gains other writers.

**Rejected.** `gh api` issue creation from the session (no email without the "Include your own
updates" setting, which emails you about every comment you write anywhere); a `repository_dispatch`
trigger (no safer at this trust level, and it adds a call the session might lack permission for);
a separate weekly scheduled task (the daily run checks `status` instead).
