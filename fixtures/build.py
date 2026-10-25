#!/usr/bin/env python3
"""Regenerate the offline fixtures: python3 fixtures/build.py (from the repository root).

Synthetic, clearly-fictional items in each real feed format, one file per enabled source in
fixtures/feeds/, plus the starting state in fixtures/state/ that makes a dry run exercise
dedupe, cross-source merging, a page-watch change and failing sources. A `.error` file makes
that source fail with the file's text.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from techdigest.parse import page_hash, page_paragraphs, paragraph_hashes  # noqa: E402
from techdigest.urls import canonical_key  # noqa: E402

FEEDS = ROOT / "fixtures/feeds"
STATE = ROOT / "fixtures/state"
NOW = "2026-10-23T11:30:00Z"  # 06:30 in Chicago

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
<title>{title}</title>
{entries}
</feed>
"""
RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>{title}</title>
{items}
</channel></rss>
"""


def atom_entry(title, url, date, summary="", content=None, media=None):
    body = f"<content type=\"html\">{content}</content>" if content else \
        (f"<summary>{summary}</summary>" if summary else "")
    group = f"<media:group><media:description>{media}</media:description></media:group>" if media else ""
    return (f"<entry><id>{url}</id><title>{title}</title>"
            f"<link rel=\"alternate\" href=\"{url}\"/><published>{date}</published>"
            f"<updated>{date}</updated>{body}{group}</entry>")


def rss_item(title, url, date, desc="", encoded=None):
    enc = f"<content:encoded><![CDATA[{encoded}]]></content:encoded>" if encoded else ""
    return (f"<item><title>{title}</title><link>{url}</link><guid>{url}</guid>"
            f"<pubDate>{date}</pubDate><description>{desc}</description>{enc}</item>")


def hn(hits):
    return json.dumps({"hits": hits}, indent=1)


def hit(oid, title, url, points, comments, ts=1792742400, text=None):  # 2026-10-23T08:00Z
    h = {"objectID": str(oid), "title": title, "url": url, "points": points,
         "num_comments": comments, "created_at_i": ts}
    if text:
        h["story_text"] = text
    return h


LISTING = """<!doctype html><html><body><nav><a href="/news/announcements">Announcements</a></nav>
<main>{links}</main><footer><a href="/legal/privacy">Privacy</a></footer></body></html>"""

CWS_OLD = """<html><body><nav>Docs menu</nav><main>
<h1>Program policies (fixture)</h1>
<p>Extensions must have a single purpose that is narrow and easy to understand.</p>
<p>Extensions must disclose the data they collect in the privacy fields of the dashboard.</p>
<p>Remote code execution is not allowed in Manifest V3 extensions.</p>
</main><footer>Footer links</footer></body></html>"""
CWS_NEW = CWS_OLD.replace(
    "<p>Remote code execution is not allowed in Manifest V3 extensions.</p>",
    "<p>Remote code execution is not allowed in Manifest V3 extensions.</p>\n"
    "<p>From January 2027, extensions that use on-device AI models must say so in their store "
    "listing (fixture text).</p>")
AMO = """<html><body><main><h1>Add-on policies (fixture)</h1>
<p>Add-ons must not contain obfuscated code.</p><p>Add-ons must respect user privacy.</p>
</main></body></html>"""

FILES = {
    "anthropic-news.html": LISTING.format(links="""
<a href="/news/fixture-old-post"><h3>An older announcement (fixture)</h3></a>
<a href="/news/claude-fixture-pricing"><img alt="Claude API pricing changes for batch and caching (fixture)" src="x.png"><span>Product</span></a>
<a href="/news/claude-fixture-pricing"><h3>Claude API pricing changes for batch and caching (fixture)</h3><span>Oct 22, 2026</span></a>
"""),
    "anthropic-engineering.html": LISTING.format(links="""
<a href="/engineering/fixture-old">Old engineering post (fixture)</a>
<a href="/engineering/fixture-subagent-evals"><h2>How we evaluate subagent hand-offs in Claude Code (fixture)</h2></a>
"""),
    "claude-code-releases.md": """# Changelog

## 9.9.1

- Added a fixture-only flag to skills
- Fixed subagent context compaction in long sessions

## 9.9.0

- Already seen in the fixture state
""",
    "simon-willison.atom": ATOM.format(title="Simon Willison's Weblog", entries="\n".join([
        atom_entry("Notes on a fixture context-engineering pattern",
                   "https://simonwillison.net/2026/Oct/22/fixture-context/?utm_source=rss",
                   "2026-10-22T18:00:00Z",
                   summary="&lt;p&gt;A write-up of keeping CLAUDE.md short and moving procedures into skills, with token counts.&amp;nbsp;Fixture text.&lt;/p&gt;"),
        atom_entry("Quoting a fixture model card", "https://simonwillison.net/2026/Oct/22/fixture-quote/",
                   "2026-10-22T09:00:00Z", summary="A short quotation about pricing per million tokens (fixture)."),
        atom_entry("Something from last month", "https://simonwillison.net/2026/Sep/01/old/",
                   "2026-09-01T09:00:00Z", summary="Out of the window."),
    ])),
    "hn-front.json": hn([
        hit(1000001, "Notes on a fixture context-engineering pattern",
            "https://simonwillison.net/2026/Oct/22/fixture-context/", 412, 230),
        hit(1000002, "A fixture database that runs in WebGPU", "https://example.org/webgpu-db", 310, 120),
        hit(1000003, "Ask HN: An already-seen fixture question", None, 200, 300),
    ]),
    "hn-keywords.json": hn([
        hit(1000004, "Running small vision models in the browser with ONNX (fixture)",
            "https://example.org/onnx-vision", 88, 40),
        hit(1000005, "A fixture story about gardening", "https://example.org/garden", 95, 12),
    ]),
    "hn-show.json": hn([
        hit(1000006, "Show HN: A fixture deck builder for card games, $2k MRR",
            "https://example.org/deck-builder", 150, 60,
            text="I built this solo over six months. Fixture text."),
    ]),
    "reddit.error": "HTTP 429",
    "yt-anthropic.atom": ATOM.format(title="Anthropic", entries=atom_entry(
        "Building agents with skills (fixture talk)", "https://www.youtube.com/watch?v=FixtureAAAA",
        "2026-10-22T16:00:00Z", media="A talk on packaging procedures as skills. Fixture description.")),
    "yt-ai-engineer.error": "HTTP 404",
    "yt-latent-space.error": "HTTP 404",
    "yt-ai-explained.error": "HTTP 404",
    "arxiv.atom": ATOM.format(title="arXiv Query", entries="\n".join([
        atom_entry("Measuring Harness Effects on\n  Coding Agent Benchmarks (fixture)",
                   "http://arxiv.org/abs/2610.99001v2", "2026-10-22T17:00:00Z",
                   summary="We show that the agent harness changes SWE-bench scores by up to 9 points. Fixture abstract."),
        atom_entry("An unrelated fixture paper", "http://arxiv.org/abs/2610.99002v1",
                   "2026-10-22T17:00:00Z", summary="Fixture abstract."),
    ])),
    "latent-space.rss": RSS.format(title="Latent Space", items=rss_item(
        "Inside a coding-agent eval team (fixture)", "https://www.latent.space/p/fixture-evals",
        "Thu, 22 Oct 2026 14:00:00 GMT", desc="<![CDATA[<p>An interview about evals&nbsp;for agents.</p>]]>")),
    "hf-blog.rss": RSS.format(title="Hugging Face Blog", items=rss_item(
        "transformers.js adds WebGPU vision pipelines (fixture)", "https://huggingface.co/blog/fixture-webgpu",
        "Thu, 22 Oct 2026 12:00:00 GMT", desc="Fixture post about running detection models in the browser.")),
    "transformers-js-releases.json": json.dumps({"name": "@huggingface/transformers", "time": {
        "created": "2023-01-01T00:00:00Z", "modified": "2026-10-22T10:00:00Z",
        "4.8.0": "2026-09-01T10:00:00Z", "4.9.0-next.1": "2026-10-20T10:00:00Z",
        "4.9.0": "2026-10-22T10:00:00Z"}}, indent=1),
    "chrome-dev-blog.rss": RSS.format(title="Chrome for Developers", items=rss_item(
        "What's new in the side panel API (fixture)", "https://developer.chrome.com/blog/fixture-side-panel",
        "Wed, 22 Oct 2026 16:00:00 GMT", desc="Extensions can now open the side panel from a context menu. Fixture.")),
    "mozilla-addons-blog.rss": RSS.format(title="Mozilla Add-ons Blog", items=rss_item(
        "Fixture: changes to add-on review times", "https://blog.mozilla.org/addons/2026/10/22/fixture-review/",
        "Wed, 22 Oct 2026 15:00:00 +0000", encoded="<p>Review queues are shorter this quarter. Fixture.</p>")),
    "cws-policy.html": CWS_NEW,
    "amo-policy.html": AMO,
    "riftbound-news.html": LISTING.format(links="""
<a href="/en-us/news/announcements/fixture-community-tools"><div><span>Announcements</span><span>Updates to our community tools guidelines for Riftbound (fixture).</span></div></a>
"""),
    "optcg-news.html": LISTING.format(links="""
<a href="https://en.onepiece-cardgame.com/news/fixture-261020.html"><span class="date">October 20, 2026</span><span class="text">Fixture notice about card data use by fan sites</span></a>
"""),
    "openai-news.rss": RSS.format(title="OpenAI News", items=rss_item(
        "A fixture model price cut", "https://openai.com/index/fixture-price-cut",
        "Thu, 22 Oct 2026 17:00:00 GMT", desc="Prices for a fixture model drop by half.")),
    "deepmind-blog.rss": RSS.format(title="Google DeepMind", items=rss_item(
        "A fixture on-device model", "https://deepmind.google/discover/blog/fixture-on-device/",
        "Thu, 22 Oct 2026 13:00:00 GMT", desc="A small model for phones. Fixture.")),
}


PARSE_ONLY = {  # parser fixtures not tied to a configured source
    "github-releases.atom": ATOM.format(title="Release notes from claude-code", entries="\n".join([
        atom_entry("v9.9.1", "https://github.com/anthropics/claude-code/releases/tag/v9.9.1",
                   "2026-10-22T20:00:00Z", content="&lt;h2&gt;What's changed&lt;/h2&gt;&lt;ul&gt;"
                   "&lt;li&gt;Added a fixture-only flag to skills&lt;/li&gt;&lt;li&gt;Fixed subagent "
                   "context compaction in long sessions&lt;/li&gt;&lt;/ul&gt;"),
        atom_entry("v9.9.0", "https://github.com/anthropics/claude-code/releases/tag/v9.9.0",
                   "2026-10-15T20:00:00Z", content="Too old for the window"),
    ])),
}


def main():
    FEEDS.mkdir(parents=True, exist_ok=True)
    parse_dir = ROOT / "fixtures/parse"
    parse_dir.mkdir(parents=True, exist_ok=True)
    for name, text in PARSE_ONLY.items():
        (parse_dir / name).write_text(text.strip() + "\n", encoding="utf-8")
    for old in FEEDS.iterdir():
        old.unlink()
    for name, text in FILES.items():
        (FEEDS / name).write_text(text.strip() + "\n", encoding="utf-8")
    (ROOT / "fixtures/now.txt").write_text(NOW + "\n")

    STATE.mkdir(parents=True, exist_ok=True)
    seen = {k: "2026-10-01" for k in [
        canonical_key("https://www.anthropic.com/news/fixture-old-post"),
        canonical_key("https://www.anthropic.com/engineering/fixture-old"),
        "hn:1000003",
        "changelog:claude-code-releases:9.9.0",
    ]}
    (STATE / "seen.json").write_text(json.dumps({"version": 1, "items": seen}, indent=1, sort_keys=True) + "\n")

    def page(html):
        paras = page_paragraphs(html)
        return {"hash": page_hash(paras), "paras": paragraph_hashes(paras),
                "changed": "2026-09-30", "checked": "2026-10-22"}

    boot = {"bootstrapped": "2026-10-01", "last_ok": "2026-10-22"}
    sources = {"sources": {
        "anthropic-news": boot, "anthropic-engineering": boot,
        "riftbound-news": boot, "optcg-news": boot, "claude-code-releases": boot,
        "cws-policy": {**boot, "page": page(CWS_OLD)},
        "amo-policy": {**boot, "page": page(AMO)},
    }}
    (STATE / "sources.json").write_text(json.dumps(sources, indent=1, sort_keys=True) + "\n")
    print(f"wrote {len(FILES)} feeds, now.txt and state/ under fixtures/")


if __name__ == "__main__":
    main()
