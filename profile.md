# What I already have

The reviewer measures each item against this file, so its cards can say "this would replace X",
"you already do this" or "this fits project Y". `interests.md` says what to show; this file says
what I'm working with. Edit freely.

**This repository is public**, so this file describes each project only as far as its public
README or site does. Nothing here is secret.

## Projects

<!-- One line per project, as `- Name: description`. Card `fits` values must be one of these
names, exactly; techdigest/cards.py reads this section. -->

- Claude Code workflow: how I work day to day: Claude Code in the desktop app and CLI, cloud scheduled tasks, subagents, skills, plans and review gates.
- workflow kit: claude-workflow, the repo-committed kit (agents, skills, branch guard, decisions record, check) installed in my repos at light or full level.
- RiftSight: Chrome extension, relay backend and web tools that make Riftbound gameplay video interactive (deck tracker, hover cards on streams, card recognition).
- riftsight-vision: open weights, labels and tools for recognising trading cards in gameplay video (small vision models, ONNX, in-browser inference).
- Kenbunshoku: Chrome extension: hover a One Piece Card Game card in a Twitch or YouTube stream to see it. Looking for a maintainer.
- DuelSight: the same hover-a-card Chrome extension for Yu-Gi-Oh! videos and streams, on the Chrome Web Store.
- StackDepth: an early-stage product (not public yet) about learning to engineer alongside AI coding tools.
- Vantle: turns decision logic in code into flowcharts, checked against the real code by tests; early prototype in TypeScript.
- cardvision-hq: my coordination repo: a daily standup page built by a scheduled agent run, and a cross-project calendar.
- tech-digest: this daily digest: a stdlib-Python fetch, Claude picks, GitHub Action delivery.

## How I build

- Solo developer. Claude Code does most of the implementation; I plan, review and merge.
- Agents work on branches, never on main; I merge. Plans before code for anything multi-step,
  with a fresh-context reviewer before "done".
- Stack: TypeScript (extensions, web tools), Python (tooling, data, ML), Chrome extensions
  (Manifest V3, side panel), ONNX Runtime Web and wasm for in-browser vision.
- Scheduled cloud tasks for recurring work: this digest, the cardvision-hq standup.

## Already tried, or ruled out

<!-- Things a card shouldn't suggest again. The weekly issue's "done" and "not for me" ticks
propose additions here by PR. -->

- Gradientless (CI for agent harnesses): archived for the foreseeable future; don't suggest reviving it.
