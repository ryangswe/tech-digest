# skill-lint (fixture)

A command-line checker for Claude Code skills: it validates SKILL.md frontmatter, flags
descriptions that never name a trigger situation, and finds skills no CLAUDE.md or agent mentions.

## Install

Run it with npx; it needs Node 20. It reads `.claude/skills/` and exits non-zero on problems, so it
can run in CI next to other checks. The README says it was built after a skill silently never
loaded for a month because its description named the output rather than the situation.
