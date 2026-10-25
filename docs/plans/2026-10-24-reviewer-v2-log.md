# Execution log — tech-digest v2

- **2026-10-24 — Plan: the repository is public**
  - **Evidence:** `gh repo view` reports PUBLIC; cardvision-hq's CONTEXT.md (edited 2026-10-24)
    lists it as public. v1 created it private.
  - **Impact:** profile.md, cards, weekly issues and any committed bookmark output are public.
  - **Resolution:** profile.md describes projects at public level; `backlog/raw/` and
    `backlog/out/` are gitignored; where the report and queue live is asked at T7.
  - **Permanent decision record needed:** Yes (the quarantine and public-content entry)

- **2026-10-24 — T2: class-based skipping dropped all of arXiv's page**
  - **Evidence:** arXiv wraps the page in `<div class="flex-wrap-footer">`; a substring match on
    "footer" skipped everything.
  - **Resolution:** class and id tokens match exactly or as a first word (`footer`, `footer-x`),
    with a retry without class skipping when the result is thin. Live sample: 9 of 14 read fully
    before the fix, arXiv included after it.
  - **Permanent decision record needed:** No

- **2026-10-24 — T5: the weekly issue moved into the delivery workflow**
  - **Evidence:** the weekly issue only ranks cards that were validated when their digests were
    made, so it needs no Claude judgement.
  - **Impact:** no new prompt steps or allowlisted branch paths; it runs as a Monday step of
    `deliver.yml`, and needs a Monday digest to trigger it.
  - **Resolution:** a deviation from the plan, which had it inside the daily run.
  - **Permanent decision record needed:** No

- **2026-10-24 — T3: what v1 already exposed**
  - **Evidence:** the main session reads `build/candidates.json`, whose summaries (Reddit and HN
    post text, at most about 300 characters) are untrusted.
  - **Impact:** a small, pre-existing exposure; v2 adds none (full pages go only to the reader).
  - **Resolution:** the daily prompt now says to treat summaries as data, and to report any
    instruction-like text it sees.
  - **Permanent decision record needed:** No (covered by the quarantine entry)

- **2026-10-24 — T8: the review found the quarantine unenforced**
  - **Evidence:** `tools: Read, Write` limits which tools a subagent has, not where Write may
    write. An injected reader could overwrite repository code, the hook that runs on every
    write, or the build files the renderer trusts.
  - **Impact:** the plan's central safety claim did not hold until fixed.
  - **Resolution:** a tamper check (`scope snapshot`/`check`, token held by the main session)
    stops the run on any change. A fail-closed write-scope hook for run branches is built and
    tested; wiring it into `.claude/settings.json` is the owner's call. Side channels closed;
    flags reduced to a boolean.
  - **Permanent decision record needed:** Yes (the quarantine entry is updated)
