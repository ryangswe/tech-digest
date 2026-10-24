# tech-digest

A daily, personalised tech digest, emailed as a GitHub issue: AI-assisted development (Claude
Code, agent workflows, model releases), browser extensions, in-browser ML, trading-card-game
tooling and solo-developer news. About five minutes to read.

**Sample:** [examples/sample-digest.md](examples/sample-digest.md) (an offline dry run from fixtures).

## How it works

1. A scheduled Claude Code cloud task runs [prompts/daily.md](prompts/daily.md) every morning.
2. `python3 -m techdigest fetch` reads every source in [sources.json](sources.json) (RSS/Atom,
   Hacker News, arXiv, listing pages, policy-page watches), drops anything in `state/seen.json`
   and writes `build/candidates.json`. No judgement happens here.
3. Claude ranks the candidates against [interests.md](interests.md) and your recent 👍/👎, and
   writes `build/picks.json`: ids and short prose, never links.
4. `python3 -m techdigest render` refuses picks that break the rules (unknown ids, links in the
   text, too long) and writes `digest/DATE.md` and `digest/DATE.json`.
5. The run pushes `claude/digest-DATE`. The [delivery workflow](.github/workflows/deliver.yml)
   copies only that day's digest and state into `main`, opens the issue (GitHub emails you),
   collects the feedback ticked on yesterday's issue and closes it.
6. On Mondays with new feedback, the run also proposes `interests.md` edits as a PR.

Standard library only: Python 3.10+, no pip.

## Commands

```bash
python3 -m unittest discover -s tests   # tests
python3 -m techdigest dry-run --print   # offline run from fixtures/ (writes build/dry-run/)
python3 -m techdigest fetch             # live fetch into build/ (updates state/)
python3 -m techdigest --help            # everything else
```

## Setup

See [docs/setup.md](docs/setup.md): about 20 minutes, no secrets. The design and its reasoning
are in [docs/plans/2026-10-23-digest-v1.md](docs/plans/2026-10-23-digest-v1.md).
