# Setup: the steps only the owner can do

About 20 minutes, once, after the `digest-v1` work is merged into `main`. Nothing here needs a
secret, an API key or a connector.

## 1. Let cloud sessions reach this repository (2 min)

github.com/apps/claude → **Configure** → your account → under *Repository access*, add
`ryangswe/tech-digest` (skip this if it already says *All repositories*).

## 2. Create the cloud environment (5 min)

claude.ai/code → open any cloud session's environment menu (or, later, the scheduled task's
*Edit → Advanced settings → General → Cloud environment*) → **Add environment**:

- **Name:** `tech-digest`
- **Network access:** **Custom**. Keep **"Also include default list of common package
  managers"** ticked. That list already covers `github.com`, `api.github.com` and
  `raw.githubusercontent.com`.
- **Allowed domains** (one per line):

  ```
  www.anthropic.com
  simonwillison.net
  hn.algolia.com
  www.reddit.com
  www.youtube.com
  export.arxiv.org
  www.latent.space
  huggingface.co
  developer.chrome.com
  blog.mozilla.org
  extensionworkshop.com
  openai.com
  deepmind.google
  riftbound.leagueoflegends.com
  en.onepiece-cardgame.com
  ```

- **Environment variables:** none. **Network secrets:** none. **Setup script:** none.

When you add a source to `sources.json` (for example by filling in a placeholder), add its host
here too. A missing host shows in the digest's footer as `HTTP 403 (host_not_allowed)`.

## 3. Create the scheduled task (5 min)

claude.ai/code/routines → **New task** → **Set up manually**:

- **Name:** `tech-digest daily`
- **Repository:** `ryangswe/tech-digest`
- **Environment:** `tech-digest`
- **Schedule:** Daily at **06:37**. The scheduler takes your local time zone: use
  **America/Chicago**, the same zone as `"timezone"` in `sources.json`. If you move, change both.
- **Model:** Sonnet 5.5 (pick it in the prompt box's model selector).
- **Connectors:** remove all of them; the run needs none.
- **Prompt:**

  ```
  You are the scheduled daily run of ryangswe/tech-digest, in a fresh clone of the repository.
  Read CLAUDE.md, then follow prompts/daily.md exactly, step by step. This run is unattended:
  never ask questions, never push to main, never open a PR except the weekly interests PR that
  prompts/daily.md describes, and never edit any file outside digest/, state/ and build/ (plus
  interests.md, only on a claude/interests-* branch). If a step fails, follow the failure rules
  in prompts/daily.md and end the run.
  ```

## 4. Check you will get the email (1 min)

github.com/settings/notifications → under **Watching**, **Email** is ticked (the default). On the
repository page, the **Watch** button shows *All Activity* or *Participating and @mentions* plus
*Issues* under *Custom*. You created the repository, so you are watching it already.

Issues are opened by `github-actions[bot]`, so they email you. Closing yesterday's issue may
send a second, shorter notification; if that bothers you, say so and it can be changed.

## 5. First run (5 min)

On the task's page, **Run now**. Within about 10 minutes:

- the run's transcript ends with a summary (a green status alone does not prove it pushed);
- the repository's **Actions** tab shows *Deliver digest* succeeding;
- an issue "☕ Tech Digest — …" arrives by email.

The first run's digest is thin by design: listing pages without dates (Anthropic News and
Engineering, Riftbound, One Piece TCG) record today's links as already seen, and page watches
record a baseline. From the second day, only new items appear.

## Later, when you want

- **Fill the placeholders** in `sources.json` (the Riftbound and One Piece TCG policy pages, your
  extensions): paste the URL, set `"enabled": true`, add the host to step 2's list, and add a
  fixture in `fixtures/build.py` (a test checks every enabled source has one).
- **Edit `interests.md`** whenever you like. The weekly run proposes changes as a PR.
- **Running locally on this Mac**: the python.org Python has no CA certificates, so run
  `/Applications/Python\ 3.10/Install\ Certificates.command` once, or prefix commands with
  `SSL_CERT_FILE=/etc/ssl/cert.pem`. The One Piece TCG site still fails locally with the macOS
  bundle (its root certificate is newer); the cloud image's bundle has it.

## If something goes wrong

| You see | Likely cause | Fix |
|---|---|---|
| A "No digest today" issue | The run failed or stalled | Open the task's latest run transcript |
| "Digest run failed: claude/digest-…" | The delivery workflow refused the branch | The issue quotes the log; the branch is kept |
| Footer: many `HTTP 403 (host_not_allowed)` | A host is missing from the allowlist | Step 2 |
| Footer: YouTube `HTTP 404` | YouTube's channel feeds are down (widely reported since late 2025) | Wait, or switch to the YouTube Data API (needs a free key) |
| Footer: Reddit `HTTP 429` or `403` | Reddit blocks unauthenticated feeds | Ignore, or disable the source |
