<!-- A rehearsal of prompts/daily.md by Sonnet 5.5 on live data, 2026-10-23, before the footer and prompt fixes that followed it. Not delivered. -->

# ☕ Tech Digest — Fri 23 Oct 2026

_A quiet-ish Friday for Anthropic's own blogs, so the Claude Code changelog and a pile of agent papers carry the day._

## 🏆 Top 3

### 1. Anthropic donates the Agent Skills standard to the Agentic AI Foundation

Per Simon Willison quoting Anthropic's announcement: Anthropic says it is committed to keeping Agent Skills open, community-driven and vendor-neutral. It is donating the standard to the Agentic AI Foundation (AAIF) under the Linux Foundation, which it co-founded with Block.

**Why it matters to you:** Skills sit at the top of your interests list. A standard held by a neutral foundation, not one vendor, is the kind of change worth knowing about before you build on skills.

[Simon Willison](https://simonwillison.net/2026/Oct/22/donating-agent-skills/)

### 2. Claude Code v2.1.310 fixes compaction after 'Prompt is too long' errors

The release adds the Monitor tool and plugin monitors on Bedrock, Vertex and Foundry. It fixes compaction after a 'Prompt is too long' error keeping too much of a dense conversation, such as base64 or SVG, so the next request could fail again. It also fixes hooks letting a tool call through on Windows when Git Bash is missing, and improves memory use of non-interactive sessions during compaction.

**Why it matters to you:** Context compaction and hooks are both on your want list, and the compaction fix is the kind of change that decides whether a long session survives.

[Claude Code releases](https://github.com/anthropics/claude-code/releases/tag/v2.1.310)

### 3. ProductWebBench grades frontend coding agents on whether the rest of the site still works

The paper says frontend coding agents are usually graded only on whether the requested target got built. It calls the second obligation, keeping the rest of the site working, website continuity, and introduces ProductWebBench, a benchmark for it.

**Why it matters to you:** Evals for coding agents are on your want list, and this one questions what existing benchmarks measure, which is useful when you ship browser tools with an agent.

[arXiv](https://arxiv.org/abs/2610.31118)

## 👀 Worth a skim

- Kimi K3.1 Pro is on the Kimi API. Weights are not open yet, but Moonshot promises them by Nov 4, 2026. A Highspeed version is 2-3x faster at twice the price. ([Simon Willison](https://simonwillison.net/2026/Oct/23/kimi-k31-pro/))
- A r/ClaudeCode poster notices that some Kimi K3.1 Pro coding benchmarks use Claude Code as the harness. ([Reddit](https://www.reddit.com/r/ClaudeCode/comments/1xdljo1/kimi_k31_pro_benchmarks_running_on_claude_code/))
- Paper on adaptive skill granularity for coding agents, which studies what happens when reusable skills meet execution, with runtime routing and macro-to-micro recovery. ([arXiv](https://arxiv.org/abs/2610.31461))
- RIPPLE paper: coding agents often write a plausible critique of a failure and then repeat it. The authors call this the Critique-to-Action Handoff Gap and propose a training framework for recovery. ([arXiv](https://arxiv.org/abs/2610.31276))
- Experience report on a compliance-critical exam-grading system built by one developer who wrote no code by hand, under a gated process. Its title argues evaluation gets scarce when code gets cheap. ([arXiv](https://arxiv.org/abs/2610.30916))

## 🔧 Changed in my tools

- Claude Code v2.1.309: fixes sandboxed Bash commands running the shell's startup files outside the sandbox, and macOS sandbox denyWrite globs not applying through symlinks. ([Claude Code releases](https://github.com/anthropics/claude-code/releases/tag/v2.1.309))
- Claude Code v2.1.307: adds /claude-api api-version to move Claude API code to API version 2026-10-21, and a claude\_code.safety\_event OpenTelemetry event for tool calls that a rule, auto mode, hook or the sandbox stopped or prompted. ([Claude Code releases](https://github.com/anthropics/claude-code/releases/tag/v2.1.307))

<details><summary>👍 / 👎 — tick any; a weekly run learns from them</summary>

- [ ] 👍 Anthropic donates the Agent Skills standard to the Agentic AI Foundat… <!-- id:5107c05a5a -->
- [ ] 👎 Anthropic donates the Agent Skills standard to the Agentic AI Foundat… <!-- id:5107c05a5a -->
- [ ] 👍 Claude Code v2.1.310 fixes compaction after 'Prompt is too long' erro… <!-- id:2c910ba23e -->
- [ ] 👎 Claude Code v2.1.310 fixes compaction after 'Prompt is too long' erro… <!-- id:2c910ba23e -->
- [ ] 👍 ProductWebBench grades frontend coding agents on whether the rest of… <!-- id:2b6d351b01 -->
- [ ] 👎 ProductWebBench grades frontend coding agents on whether the rest of… <!-- id:2b6d351b01 -->
- [ ] 👍 Simon Willison: Introducing Kimi K3.1 Pro <!-- id:aa97060095 -->
- [ ] 👎 Simon Willison: Introducing Kimi K3.1 Pro <!-- id:aa97060095 -->
- [ ] 👍 Reddit: Kimi K3.1 Pro benchmarks running on Claude Code <!-- id:67753e7c6f -->
- [ ] 👎 Reddit: Kimi K3.1 Pro benchmarks running on Claude Code <!-- id:67753e7c6f -->
- [ ] 👍 arXiv: Adaptive Skill Granularity for Coding Agents: Runtime Routing… <!-- id:5c5a626a2b -->
- [ ] 👎 arXiv: Adaptive Skill Granularity for Coding Agents: Runtime Routing… <!-- id:5c5a626a2b -->
- [ ] 👍 arXiv: RIPPLE: Recovery Internalization through Process-Level Policy… <!-- id:80a743c9a9 -->
- [ ] 👎 arXiv: RIPPLE: Recovery Internalization through Process-Level Policy… <!-- id:80a743c9a9 -->
- [ ] 👍 arXiv: When Code Gets Cheap, Evaluation Gets Scarce: An Experience Re… <!-- id:4ac91b036d -->
- [ ] 👎 arXiv: When Code Gets Cheap, Evaluation Gets Scarce: An Experience Re… <!-- id:4ac91b036d -->
- [ ] 👍 Claude Code releases: v2.1.309 <!-- id:5a0c9caff7 -->
- [ ] 👎 Claude Code releases: v2.1.309 <!-- id:5a0c9caff7 -->
- [ ] 👍 Claude Code releases: v2.1.307 <!-- id:aad95f706b -->
- [ ] 👎 Claude Code releases: v2.1.307 <!-- id:aad95f706b -->

</details>

<sub>62 new items from 19/24 sources · failed today: One Piece Card Game news (TLS certificate check failed (on macOS python.org builds, run 'Install Certificates.command' or set SSL\_CERT\_FILE)); AI Engineer (YouTube), AI Explained (YouTube), Anthropic (YouTube), Latent Space (YouTube) (HTTP 404) · ranked by Claude</sub>
