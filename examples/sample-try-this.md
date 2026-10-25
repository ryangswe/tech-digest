<!-- Cards written by a Sonnet 5.5 reader from 7 live items and 3 fixture pages (marked "fixture"), validated by `python3 -m techdigest cards`, rendered as the weekly issue renders them. Not delivered. -->

# 🧪 Try this — sample from the v2 rehearsal (2026-10-24)

_10 things worth a look, ranked by what you've liked and how small the first step is. Tick one box per card; the weekly interests review learns from them._

### 1. skill-lint (fixture)

**Try · 15m** · fits workflow kit, tech-digest · from rehearsal, 2026-10-24 · [GitHub](https://github.com/example/skill-lint)

skill-lint is a command-line checker for Claude Code skills. It validates SKILL.md frontmatter, flags descriptions that never name a trigger situation, and finds skills that no CLAUDE.md or agent mentions. It needs Node 20, reads the skills folder and exits non-zero on problems, so it can run in CI.

**Why you:** Your workflow kit ships skills into repos, and the README's origin story is a skill that never loaded because its description named output rather than situation. That is exactly the silent failure your kit's check could catch.

**First step:** Run skill-lint once over the skills in your workflow kit and see what it flags. If the findings are real, consider adding it to the kit's check and to tech-digest's CI.

- [ ] ✅ Done <!-- card:aaaaaaaa02 -->
- [ ] ⏳ Later <!-- card:aaaaaaaa02 -->
- [ ] 🙅 Not for me <!-- card:aaaaaaaa02 -->

### 2. Stale Instruction Files Override the Code in Coding Agents: A One-Sentence Fix

**Try · 15m** · fits Claude Code workflow, workflow kit · from rehearsal, 2026-10-24 · [arXiv](https://arxiv.org/abs/2610.30571)

A study of 40 Python projects where the instruction file asks for one convention and the code uses another. Claude Code and Codex CLI followed the stale file in 90.1% of choices. One sentence in the user-level instruction file giving existing code precedence raised code-following to 91.4% and test passes to 100%.

**Why you:** Your workflow kit installs instruction files into several repos, and conventions drift between them and the code. Claude Code noticed the conflict in 79 of 80 runs and still obeyed the file, so a stale line in your kit could quietly win.

**First step:** Add one sentence to your user-level CLAUDE.md saying that when a repo's instructions disagree with its existing code, the code wins and the conflict gets reported. Then watch one repo for a week.

- [ ] ✅ Done <!-- card:f0e7a1ae71 -->
- [ ] ⏳ Later <!-- card:f0e7a1ae71 -->
- [ ] 🙅 Not for me <!-- card:f0e7a1ae71 -->

### 3. \[AINews\] Kimi 3.1 Pro 104BA-2.8T: Fable-5.1-Class Open Weights narrows Closed-AI lead to 1 month... and Pro Highspeed API with 2-3× speed

**Watch · 15m** · fits Claude Code workflow, tech-digest · from rehearsal, 2026-10-24 · [Latent Space](https://latent.space/p/ainews-kimi-31/)

A Latent Space news roundup led by Kimi K3.1 Pro: a 2.8 trillion parameter mixture-of-experts model, API live, open weights promised for November 4, priced at 2 dollars input and 10 output per million tokens. It also notes MCP Tasks and Elicitations arriving in the Claude Code CLI.

**Why you:** Open weights this large are not something you will run, and the lead is a benchmark and price story with launch-promotion allegations. The Claude Code note on long-running plugin jobs and mid-task questions is the part that touches your workflow.

**First step:** Ignore the Kimi section. Check Claude Code's release notes for the Tasks and Elicitations change and see whether your scheduled tasks or plugins could use either.

- [ ] ✅ Done <!-- card:30d5039f84 -->
- [ ] ⏳ Later <!-- card:30d5039f84 -->
- [ ] 🙅 Not for me <!-- card:30d5039f84 -->

### 4. SWE-VERIFIER: Selective Verification for Cost-Efficient Coding Agents

**Watch · 15m** · fits Claude Code workflow · from rehearsal, 2026-10-24 · [arXiv](https://arxiv.org/abs/2610.30284)

SWE-Verifier is a small model trained from Qwen3.5-4B that decides when a coding agent's next action needs extra candidate sampling and verification. It verifies under 4% of steps, lifting resolution from 75.47% to 77.20% on one model at 1.09 times the cost. Model, code and data are released.

**Why you:** Gains are under two points, and it targets agent harnesses you do not run. It matters to your review-gate habit only as evidence that verifying selectively is cheaper than verifying every step. Nothing to adopt in Claude Code today.

**First step:** Keep it on the list; revisit if Claude Code or a plugin starts offering step-level verification, and skip the full paper until then.

- [ ] ✅ Done <!-- card:5c3680f8a1 -->
- [ ] ⏳ Later <!-- card:5c3680f8a1 -->
- [ ] 🙅 Not for me <!-- card:5c3680f8a1 -->

### 5. big cloud models like opus 5.5 get all the motion graphics praise, but i made this with local qwen3.8 flash next. it's very possible!

**Watch · 15m** · fits Claude Code workflow · from rehearsal, 2026-10-24 · [Reddit](https://www.reddit.com/r/LocalLLaMA/comments/1xebkti/big_cloud_models_like_opus_55_get_all_the_motion/)

From the post title and summary only: someone made a motion-graphics video with a local Qwen model and the Remotion animation framework, saying it took several prompts and steering, and that the conversation history behind the video is shared. The page itself could not be read.

**Why you:** It is a local-model showcase about video animation, which is outside your priorities. The only loose link is a visible prompt history, but nothing in your projects needs motion graphics right now.

**First step:** Skip it unless you plan release videos for your extensions; in that case read the shared conversation history once to see how much steering the result needed.

- [ ] ✅ Done <!-- card:4b7b5642bc -->
- [ ] ⏳ Later <!-- card:4b7b5642bc -->
- [ ] 🙅 Not for me <!-- card:4b7b5642bc -->

### 6. Windswept Island: 20 days into a North Atlantic island in Unity with Claude Code (WIP, part 2)

**Watch · 15m** · fits Claude Code workflow · from rehearsal, 2026-10-24 · [Reddit](https://www.reddit.com/r/ClaudeAI/comments/1xeccp0/windswept_island_20_days_into_a_north_atlantic/)

From the post title and summary only: part two of a work-in-progress log of building a North Atlantic island in Unity with Claude Code, using real Lofoten elevation data for a 4 by 5 km island. The page itself could not be read.

**Why you:** It is a game-art project, far from your extensions and tooling, and the summary suggests a progress diary rather than a method. Only worth a look if it shows how the author steers Claude Code across a long project.

**First step:** Skip unless the post describes how the author structures instructions or reviews over twenty days; if it does, note one habit worth borrowing for your own long plans.

- [ ] ✅ Done <!-- card:cb51d1bf00 -->
- [ ] ⏳ Later <!-- card:cb51d1bf00 -->
- [ ] 🙅 Not for me <!-- card:cb51d1bf00 -->

### 7. Made a rhythm game where 4 small neural nets listen to your song right in the browser tab (open source)

**Watch · 1h** · fits riftsight-vision · from rehearsal, 2026-10-24 · [Reddit](https://www.reddit.com/r/LocalLLaMA/comments/1xeia9o/made_a_rhythm_game_where_4_small_neural_nets/)

From the post title and summary only: an open-source browser rhythm runner where four small neural nets analyse your own mp3 inside the tab, the song shapes the world you run through, and nothing is uploaded. The page itself could not be read.

**Why you:** It is a working example of several small models running locally in a browser tab, which is the same shape as riftsight-vision's in-browser inference. As a game it is off topic, so treat it only as a source of loading and performance ideas.

**First step:** If the post links a repository, look at how it loads the four models and keeps the page responsive, and compare with how riftsight-vision runs ONNX in the browser.

- [ ] ✅ Done <!-- card:3e996088b5 -->
- [ ] ⏳ Later <!-- card:3e996088b5 -->
- [ ] 🙅 Not for me <!-- card:3e996088b5 -->

### 8. What the Specification Did Not Say: Specification-Oracle Gaps in Test-Graded Coding-Agent Benchmarks

**Read later · 15m** · fits Claude Code workflow, workflow kit · from rehearsal, 2026-10-24 · [arXiv](https://arxiv.org/abs/2610.30635)

A paper on specification-oracle gaps: coding-agent benchmarks whose tests need names, paths or messages the task description never states. On SWE-Milestone, 25 of 98 milestones had one, and affected units failed in 80.6% of runs against 48.4% without. The authors release an audit tool and corrected filter lists.

**Why you:** You plan before code and gate work with a fresh-context reviewer, so the same lesson applies to your own task descriptions: tests that check unstated names make agents look worse than they are. Useful if you ever compare harness variants.

**First step:** Skim the introduction and the findings on how prevalence follows how specifications were written, then note whether your own plan template states the exact names and paths its checks expect.

- [ ] ✅ Done <!-- card:3ee31c90d1 -->
- [ ] ⏳ Later <!-- card:3ee31c90d1 -->
- [ ] 🙅 Not for me <!-- card:3ee31c90d1 -->

### 9. Splitting a reviewer into a fresh-context subagent (fixture)

**Read later · 15m** · fits Claude Code workflow, workflow kit · from rehearsal, 2026-10-24 · [Fixture blog](https://example.org/blog/fresh-reviewer)

A team moved code review into a subagent that starts with no conversation history and reads only the task, the plan and the diff. Over four weeks it flagged 31 issues the in-session review missed, at about 15% more tokens per task. It has read-only tools, a fixed severity format, and the main session must fix material findings.

**Why you:** You already do this: plans first and a fresh-context reviewer before done. The new part is the evidence, plus two details to compare against your setup: read-only tools for the reviewer and a rule that material findings must be fixed and checks re-run.

**First step:** Compare your reviewer agent's tool list and output format with the post's, and check that your done rule requires fixing material findings and re-running checks.

- [ ] ✅ Done <!-- card:aaaaaaaa03 -->
- [ ] ⏳ Later <!-- card:aaaaaaaa03 -->
- [ ] 🙅 Not for me <!-- card:aaaaaaaa03 -->

### 10. Ten skills worth installing (fixture)

**Watch · 15m** · fits workflow kit · from rehearsal, 2026-10-24 · [Fixture blog](https://example.org/ten-skills) ⚠️ The source contained text aimed at AI agents; the reader ignored it.

A list of ten Claude Code skills, including a changelog writer, a test-gap finder and a dependency auditor, each with a one-line note on when it triggers. The author says descriptions that name the trigger situation load more reliably than ones that name the skill's output.

**Why you:** A plain list of skills is the kind of post you said you do not want, and your workflow kit already ships its own skills. The one useful claim is about how to write skill descriptions, and it is the author's say-so, not a measurement.

**First step:** Skip the list. Look at the descriptions of your workflow kit's skills and check whether each says when to use it rather than what it produces.

- [ ] ✅ Done <!-- card:aaaaaaaa01 -->
- [ ] ⏳ Later <!-- card:aaaaaaaa01 -->
- [ ] 🙅 Not for me <!-- card:aaaaaaaa01 -->
