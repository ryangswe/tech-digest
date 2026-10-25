import unittest

from techdigest.parse import (ParseError, page_paragraphs, parse_arxiv, parse_feed, parse_hn,
                              parse_html_links)

from techdigest.parse import parse_changelog_md, parse_npm

from helpers import ROOT, feed, src


class FeedTest(unittest.TestCase):
    def test_atom_github_releases(self):
        items = parse_feed((ROOT / "fixtures/parse/github-releases.atom").read_bytes(), src())
        self.assertEqual([i.title for i in items], ["v9.9.1", "v9.9.0"])
        self.assertIn("Fixed subagent context compaction", items[0].summary)
        self.assertNotIn("<", items[0].summary)
        self.assertEqual(items[0].published.isoformat(), "2026-10-22T20:00:00+00:00")

    def test_atom_strips_tracking_and_entities(self):
        items = parse_feed(feed("simon-willison.atom"), src())
        self.assertEqual(items[0].url, "https://simonwillison.net/2026/Oct/22/fixture-context/")
        self.assertIn("skills, with token counts. Fixture", items[0].summary)

    def test_youtube_description_from_media_group(self):
        [it] = parse_feed(feed("yt-anthropic.atom"), src())
        self.assertIn("packaging procedures as skills", it.summary)
        self.assertEqual(it.key, "youtube:FixtureAAAA")

    def test_rss_cdata_and_html_entities(self):
        [it] = parse_feed(feed("latent-space.rss"), src())
        self.assertEqual(it.summary, "An interview about evals for agents.")

    def test_rss_content_encoded(self):
        [it] = parse_feed(feed("mozilla-addons-blog.rss"), src())
        self.assertEqual(it.published.day, 22)

    def test_rss_undefined_entity_in_title_and_missing_date(self):
        raw = b"""<rss><channel><item><title>A &mdash; B &bogus;</title>
        <link>https://e.com/x</link></item></channel></rss>"""
        [it] = parse_feed(raw, src())
        self.assertEqual(it.title, "A — B &bogus;")
        self.assertIsNone(it.published)

    def test_rdf_rss1(self):
        raw = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
        <item><title>RDF item</title><link>https://e.com/rdf</link><dc:date>2026-10-22T10:00:00Z</dc:date></item>
        </rdf:RDF>"""
        [it] = parse_feed(raw, src())
        self.assertEqual((it.title, it.published.hour), ("RDF item", 10))

    def test_reddit_link_post_points_at_link_and_keeps_thread(self):
        raw = b"""<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
        <entry><category term="ClaudeAI" label="r/ClaudeAI"/><title>A link post</title>
        <link href="https://www.reddit.com/r/ClaudeAI/comments/1abc/a_link_post/"/>
        <updated>2026-10-23T01:00:00+00:00</updated>
        <content type="html">&lt;p&gt;Body text&lt;/p&gt; submitted by &lt;a href="https://www.reddit.com/user/x"&gt; /u/x &lt;/a&gt;
        &lt;br/&gt; &lt;span&gt;&lt;a href="https://example.org/article?utm_source=reddit"&gt;[link]&lt;/a&gt;&lt;/span&gt;
        &lt;span&gt;&lt;a href="https://www.reddit.com/r/ClaudeAI/comments/1abc/a_link_post/"&gt;[comments]&lt;/a&gt;&lt;/span&gt;</content>
        </entry></feed>"""
        [it] = parse_feed(raw, src(flavor="reddit"))
        self.assertEqual(it.url, "https://example.org/article")
        self.assertEqual(it.discussions[0]["name"], "r/ClaudeAI")
        self.assertEqual(it.summary, "Body text")
        self.assertIn("reddit:1abc", it.all_keys())

    def test_not_xml_raises(self):
        with self.assertRaises(ParseError):
            parse_feed(b"<html><body>Rate limited", src())

    def test_entries_without_title_or_link_dropped(self):
        raw = b"<rss><channel><item><title></title><link>https://e.com</link></item>" \
              b"<item><title>No link</title></item></channel></rss>"
        self.assertEqual(parse_feed(raw, src()), [])


class ChangelogNpmTest(unittest.TestCase):
    def test_changelog_versions_with_bullets_as_summary(self):
        s = src(type="changelog_md", title_prefix="Claude Code ",
                link_template="https://github.com/anthropics/claude-code/releases/tag/v{version}")
        items = parse_changelog_md(feed("claude-code-releases.md"), s)
        self.assertEqual([i.title for i in items], ["Claude Code 9.9.1", "Claude Code 9.9.0"])
        self.assertEqual(items[0].url, "https://github.com/anthropics/claude-code/releases/tag/v9.9.1")
        self.assertEqual(items[0].summary, "Added a fixture-only flag to skills · "
                                           "Fixed subagent context compaction in long sessions")
        self.assertEqual(items[0].key, "changelog:test:9.9.1")
        self.assertIsNone(items[0].published)

    def test_changelog_heading_forms_and_limit(self):
        raw = "# Changelog\n\n## [v1.2.0] - 2026-10-01\n- a\n\n## 1.1.0\n- b\n## 1.0.0\n- c\n"
        items = parse_changelog_md(raw, src(type="changelog_md"), limit=2)
        self.assertEqual([i.title for i in items], ["1.2.0", "1.1.0"])

    def test_changelog_without_versions_fails(self):
        with self.assertRaises(ParseError):
            parse_changelog_md("<html>blocked</html>", src(type="changelog_md"))

    def test_npm_stable_versions_newest_first(self):
        s = src(type="npm", title_prefix="transformers.js ",
                link_template="https://github.com/huggingface/transformers.js/releases/tag/{version}")
        items = parse_npm(feed("transformers-js-releases.json"), s)
        self.assertEqual([i.title for i in items], ["transformers.js 4.9.0", "transformers.js 4.8.0"])
        self.assertEqual(items[0].published.isoformat(), "2026-10-22T10:00:00+00:00")
        self.assertEqual(items[0].key, "npm:@huggingface/transformers:4.9.0")


class ArxivTest(unittest.TestCase):
    def test_ids_without_version_and_titles_collapsed(self):
        items = parse_arxiv(feed("arxiv.atom"), src(type="arxiv"))
        self.assertEqual(items[0].url, "https://arxiv.org/abs/2610.99001")
        self.assertEqual(items[0].key, "arxiv:2610.99001")
        self.assertEqual(items[0].title, "Measuring Harness Effects on Coding Agent Benchmarks (fixture)")


class HNTest(unittest.TestCase):
    def test_hits(self):
        items = parse_hn(feed("hn-front.json"), src(type="hn"))
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].points, 412)
        self.assertEqual(items[0].discussions[0]["url"], "https://news.ycombinator.com/item?id=1000001")
        ask = items[2]  # Ask HN: no url, so the thread is the link
        self.assertEqual(ask.url, "https://news.ycombinator.com/item?id=1000003")
        self.assertEqual(ask.key, "hn:1000003")

    def test_bad_json(self):
        with self.assertRaises(ParseError):
            parse_hn(b"<html>", src(type="hn"))


class HtmlLinksTest(unittest.TestCase):
    def test_heading_beats_alt_beats_text_and_relative_links_resolve(self):
        s = src(type="html_links", url="https://www.anthropic.com/news", pattern=r"^/news/[a-z0-9-]+$",
                exclude_paths=["/news/announcements"], min_title_chars=12)
        items = parse_html_links(feed("anthropic-news.html"), s)
        self.assertEqual([i.url for i in items], ["https://www.anthropic.com/news/fixture-old-post",
                                                  "https://www.anthropic.com/news/claude-fixture-pricing"])
        self.assertEqual(items[1].title, "Claude API pricing changes for batch and caching (fixture)")

    def test_absolute_links_on_same_host_and_text_spans(self):
        s = src(type="html_links", url="https://en.onepiece-cardgame.com/news/",
                pattern=r"^/news/[a-z0-9_-]+\.html$", min_title_chars=10)
        [it] = parse_html_links(feed("optcg-news.html"), s)
        self.assertEqual(it.title, "Fixture notice about card data use by fan sites")

    def test_other_hosts_ignored(self):
        s = src(type="html_links", url="https://a.com/", pattern=r"^/p/")
        raw = b'<a href="https://b.com/p/x">Other host title</a><a href="/p/y">Same host title</a>'
        self.assertEqual([i.url for i in parse_html_links(raw, s)], ["https://a.com/p/y"])


class PageTextTest(unittest.TestCase):
    def test_nav_footer_scripts_dropped(self):
        paras = page_paragraphs(b"<nav>Menu</nav><main><h1>Title</h1><p>Body one.</p>"
                                b"<script>var x</script></main><footer>Foot</footer>")
        self.assertEqual(paras, ["Title", "Body one."])


if __name__ == "__main__":
    unittest.main()
