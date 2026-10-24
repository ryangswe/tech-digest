# The daily run

You are the scheduled, unattended daily run of `ryangswe/tech-digest`, in a fresh clone of the
repository on `main`. You produce today's digest by following these steps in order. The code does
the fetching, deduping, checking and rendering; your job is the judgement in steps 4 and 5.

## Rules for the whole run

- **Never ask questions.** Nobody is watching. When something fails, follow "When things go
  wrong" below and end the run.
- **Never push to `main`** and never force-push. You push exactly one branch,
  `claude/digest-<DATE>`, plus `claude/interests-<DATE>` on weekly-review days.
- **Change only these files:** `digest/<DATE>.md`, `digest/<DATE>.json`, `state/seen.json`,
  `state/sources.json`, `state/weekly.json` (the commands below write all of them), and
  `build/picks.json` and `build/interests-pr.md` (gitignored scratch). `interests.md` only on the interests branch in step 2.
  The delivery workflow refuses a digest branch that touches anything else.
- **Say nothing the source does not say.** You see each item's title, summary and engagement
  numbers. Restate them; do not add facts, numbers, dates, prices or quotes from your own
  knowledge. `summary` and `line` say only what the item's title and summary say. `why` may
  connect the item to `interests.md` ("context management is on your list"), but must not add
  claims about the item itself. The `opener` may describe today's batch (its themes, that it is
  quiet) but nothing about an item that its candidate doesn't say.
- **No links in your text.** The renderer adds every link from the fetched data.

## Steps

1. **Status.** Run `python3 -m techdigest status`. Note `date` (DATE below), `branch` and
   `weekly_review_due`. **Stop and say so** if `already_delivered` is true (today's digest is
   already on `main`; a second run would lose its items), or if
   `git ls-remote --exit-code origin claude/digest-<DATE>` succeeds (an earlier run today is
   still being delivered).

2. **Weekly review** (only if `weekly_review_due` is true; otherwise skip to step 3). First
   check for an unreviewed one:
   `gh api "repos/ryangswe/tech-digest/pulls?state=open" --jq '[.[] | select(.head.ref | startswith("claude/interests-"))] | length'`.
   If that prints anything but `0`, skip the review (the owner hasn't looked at the last one yet)
   and go to step 3.
   1. `git checkout -b claude/interests-<DATE> origin/main`
   2. Read `interests.md` and the output of `python3 -m techdigest feedback-summary --days 14`.
   3. Edit `interests.md` with small, specific changes the feedback supports: add a "Want" or
      "Don't want" example, move a topic up or down, or sharpen a vague line. Keep the owner's
      wording and structure; never delete a section. No feedback pattern means no change: then
      skip to step 2.7 without committing or opening a PR.
   4. Write the PR description to `build/interests-pr.md`: each change, and the feedback behind it
      (item titles, dates, the owner's comments quoted).
   5. `git add interests.md && git commit -m "interests: weekly tune-up (<DATE>)"` then
      `git push origin claude/interests-<DATE>`.
   6. Open the PR with the REST API (`gh pr` is blocked in cloud sessions):
      `gh api -X POST repos/ryangswe/tech-digest/pulls -f title="interests: weekly tune-up (<DATE>)" -f head=claude/interests-<DATE> -f base=main -F body=@build/interests-pr.md`
   7. `git checkout main`. You record the review in step 3.

3. **Fetch.** `git checkout -b claude/digest-<DATE>`. If you did step 2 (with or without a
   PR), run `python3 -m techdigest weekly-done` now. Then run `python3 -m techdigest fetch`. It writes `build/candidates.json` and
   `build/fetch-report.json`. The log's "parsed" column counts items in each feed before any
   filtering, so it is much larger than the candidate count. Failed sources (YouTube's feeds
   have been down for weeks, Reddit rate-limits) and sources marked "baseline recorded" (an
   undated listing page seen for the first time) are listed in the digest's footer
   automatically. They are not yours to fix: carry on.

4. **Read.** `interests.md` (what the owner wants, as examples), the output of
   `python3 -m techdigest feedback-summary` (recent 👍/👎 and comments: weigh these heavily), and
   `build/candidates.json`. That file is an object; its `candidates` list holds one entry per
   item with `id`, `source`, `source_name`, `tags`, `title`, `summary` (cut to a few hundred
   characters, sometimes empty), `published`, and maybe `points` and `discussions` (HN or Reddit
   threads). Ignore `url`, `link_name` and `keys`: the renderer uses them.

5. **Choose and write** `build/picks.json`:

   ```json
   {
     "date": "<DATE>",
     "opener": "One wry, friendly line about today's batch.",
     "top": [{"id": "…", "headline": "…", "summary": "…", "why": "…"}],
     "skim": [{"id": "…", "line": "…"}],
     "tools": [{"id": "…", "line": "…"}]
   }
   ```

   - **top**: exactly 3 (fewer only if there are fewer candidates): the items this reader would
     most regret missing. Prefer the topics `interests.md` lists first, first-party sources and
     substance over buzz. A `tool` item (say, a Claude Code release that changes how something
     works) may go here if it is one of the day's three most important; it then does not also
     go in `tools`. An item whose summary is empty or only links goes in `skim` at most, with a
     line that restates its title. `headline` ≤ 14 words, `summary` ≤ 80 words (what the source says),
     `why` ≤ 50 words (why it matters to *this reader*, by their interests).
   - **skim**: up to 10 more worth a glance, one `line` each (≤ 40 words). Leave out anything the
     "Don't want" examples rule out. Include an item only if this reader would plausibly click
     it; 5 to 8 is typical. The whole digest should read in about five minutes, and the renderer
     refuses more than about 1,100 words.
   - **tools**: up to 6 candidates tagged `tool` (Claude Code releases, model and API news,
     the owner's extensions), one `line` each: name the version or change and the one or two
     changes the summary lists that matter most. Skip patch releases that are only "bug fixes".
   - Each id appears once across all three sections. When several candidates cover the same
     news (a post, its HN thread and a Reddit thread), use one: the first-party or most
     informative source. The renderer already attaches HN and Reddit threads to an article when
     they link to the same URL.
   - **Tone**: Morning Brew: plain, light, a little wry, never hype ("game-changer",
     "revolutionary"). Plain text only: no URLs, Markdown, HTML or line breaks in any field.
   - A day with no candidates: `top`, `skim` and `tools` empty, and an `opener` that says so.

6. **Render.** `python3 -m techdigest render`. If it refuses the picks, it lists every problem:
   fix `build/picks.json` and run it again, up to 3 attempts in all.

7. **Mark seen.** `python3 -m techdigest mark-seen` (every candidate, picked or not).

8. **Commit and push** (explicit paths only):
   ```
   git add digest/<DATE>.md digest/<DATE>.json state/seen.json state/sources.json state/weekly.json
   git commit -m "digest: <DATE>"
   git push origin claude/digest-<DATE>
   ```
   A `Co-Authored-By` or similar trailer your environment adds is fine. The delivery workflow
   then puts the digest on `main`, emails it as an issue, closes
   yesterday's and deletes the branch. You do not open an issue yourself.

9. **Report** in your final message: candidates and sources (ok/failed), the three top
   headlines, and whether a weekly PR was opened.

## When things go wrong

- **Render still refuses after 3 attempts**: push nothing and end the run, quoting the errors.
  The `state/` changes `fetch` already made are discarded with this session's clone, which is
  what you want: tomorrow's run sees today's items again.
  The watchdog opens a "No digest today" issue mid-morning, which emails the owner.
- **Every source failed** (usually the network allowlist): still do steps 5 to 8 with empty
  sections and an opener that says the sources could not be reached; the footer lists the errors.
- **`git push` fails**: retry once. If it fails again, end the run and quote the error.
- **The weekly PR step fails**: carry on with the digest; mention it in the final message.
