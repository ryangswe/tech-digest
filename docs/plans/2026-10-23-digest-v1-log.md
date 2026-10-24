# Execution log — tech-digest v1

- **2026-10-23 — T2: YouTube channel feeds return 404 for every channel**
  - **Evidence:** `youtube.com/feeds/videos.xml?channel_id=…` returned 404 for Anthropic, AI
    Engineer, Latent Space, AI Explained and Google Developers, from curl and Python, with
    browser and bot User-Agents. Public reports since late 2025 say the endpoint is unreliable;
    one from early October 2026 says it 404s for all channels.
  - **Impact:** the four YouTube sources fail daily for now; the footer groups them as one entry.
  - **Resolution:** kept enabled so they work again if YouTube restores the feeds. Fallback: the
    YouTube Data API v3 (free key, about 1 quota unit per channel per day), which needs an owner
    step (Google Cloud key plus a network secret for `www.googleapis.com`).
  - **Permanent decision record needed:** No

- **2026-10-23 — T2: listing pages bootstrap on first sight**
  - **Evidence:** the Anthropic News, Anthropic Engineering, Riftbound and One Piece TCG pages
    carry no dates, so the first fetch would emit every visible link (about 55) as "new".
  - **Impact:** the first live digest is thinner; from day two only new links appear.
  - **Resolution:** an undated `html_links` source records its current links as seen on its first
    successful fetch (`state/sources.json` → `bootstrapped`). Page watches record a baseline the same way.
  - **Permanent decision record needed:** No

- **2026-10-23 — T8: local-only TLS gaps on the owner's Mac**
  - **Evidence:** the python.org Python 3.10 has no CA bundle, so every source failed until
    `SSL_CERT_FILE=/etc/ssl/cert.pem` was set. en.onepiece-cardgame.com still fails with that bundle
    (its GlobalSign R46 root is missing from macOS's `cert.pem`), while curl and OpenSSL verify it.
  - **Impact:** none for the cloud run (Ubuntu's ca-certificates). Not verified from the cloud image.
  - **Resolution:** `net.py` gives a clear message for certificate failures and does not retry
    them; `docs/setup.md` covers local runs.
  - **Permanent decision record needed:** No

- **2026-10-23 — T5: trigger choice for the delivery workflow**
  - **Evidence:** push-triggered workflows run the YAML from the pushed branch; anything with
    push access can already change it, and the cloud proxy allows pushes to `main`.
  - **Resolution:** kept the push trigger and recorded the trust boundary in
    `docs/decisions/architecture.md`: the allowlist stops mistakes, and branch protection (a paid
    plan for private repositories) would be needed to stop a hostile writer.
  - **Permanent decision record needed:** Yes (done)
