import unittest
from datetime import datetime, timezone

from techdigest.text import (html_to_text, local_now, matches_any, parse_date, truncate,
                             _us_dst)
from techdigest.urls import canonical_key, clean_url


class CanonicalKeyTest(unittest.TestCase):
    def test_same_page_same_key(self):
        a = canonical_key("https://www.Example.com/post/?utm_source=rss&utm_medium=x#comments")
        b = canonical_key("http://example.com/post")
        self.assertEqual(a, b)

    def test_meaningful_query_kept_and_sorted(self):
        self.assertEqual(canonical_key("https://e.com/p?b=2&a=1"), canonical_key("https://e.com/p?a=1&b=2"))
        self.assertNotEqual(canonical_key("https://e.com/p?id=1"), canonical_key("https://e.com/p?id=2"))

    def test_arxiv_versions_and_pdf_collapse(self):
        for u in ("https://arxiv.org/abs/2610.12345v3", "http://arxiv.org/pdf/2610.12345v1",
                  "https://export.arxiv.org/abs/2610.12345"):
            self.assertEqual(canonical_key(u), "arxiv:2610.12345")

    def test_youtube_forms_collapse(self):
        for u in ("https://www.youtube.com/watch?v=abcdefghijk&t=10",
                  "https://youtu.be/abcdefghijk", "https://m.youtube.com/watch?v=abcdefghijk"):
            self.assertEqual(canonical_key(u), "youtube:abcdefghijk")

    def test_hn_and_reddit_threads(self):
        self.assertEqual(canonical_key("https://news.ycombinator.com/item?id=42"), "hn:42")
        self.assertEqual(canonical_key("https://old.reddit.com/r/ClaudeAI/comments/1abc/title/"),
                         "reddit:1abc")

    def test_clean_url_strips_tracking_only(self):
        self.assertEqual(clean_url("https://e.com/p?utm_source=x&id=3#frag"), "https://e.com/p?id=3")


class TextTest(unittest.TestCase):
    def test_html_to_text(self):
        self.assertEqual(html_to_text("<p>Hello&nbsp;<b>world</b></p><script>x()</script><p>Two</p>"),
                         "Hello world Two")

    def test_truncate_on_word_boundary(self):
        self.assertEqual(truncate("one two three four", 12), "one two…")
        self.assertEqual(truncate("short", 12), "short")

    def test_keywords_match_whole_words(self):
        self.assertEqual(matches_any("Claude Code ships MCP", ["mcp", "claude code", "cod"]),
                         ["mcp", "claude code"])
        self.assertEqual(matches_any("transformers.js 4.0", ["transformers.js"]), ["transformers.js"])

    def test_parse_dates(self):
        utc = timezone.utc
        self.assertEqual(parse_date("Thu, 22 Oct 2026 14:00:00 GMT"), datetime(2026, 10, 22, 14, tzinfo=utc))
        self.assertEqual(parse_date("2026-10-22T09:00:00-05:00"), datetime(2026, 10, 22, 14, tzinfo=utc))
        self.assertEqual(parse_date("2026-10-22T14:00:00.123456789Z").hour, 14)
        self.assertEqual(parse_date("2026-10-22T14:00:00.12Z").microsecond, 120000)
        self.assertIsNone(parse_date("not a date"))
        self.assertIsNone(parse_date(None))

    def test_us_dst_fallback(self):
        # Chicago: DST from 2026-03-08 08:00 UTC to 2026-11-01 07:00 UTC.
        self.assertFalse(_us_dst(datetime(2026, 3, 8, 7, 59, tzinfo=timezone.utc), 6))
        self.assertTrue(_us_dst(datetime(2026, 3, 8, 8, 0, tzinfo=timezone.utc), 6))
        self.assertTrue(_us_dst(datetime(2026, 11, 1, 6, 59, tzinfo=timezone.utc), 6))
        self.assertFalse(_us_dst(datetime(2026, 11, 1, 7, 0, tzinfo=timezone.utc), 6))

    def test_local_date_in_chicago(self):
        # 03:00 UTC on the 23rd is still the evening of the 22nd in Chicago.
        self.assertEqual(local_now("America/Chicago", datetime(2026, 10, 23, 3, tzinfo=timezone.utc)).day, 22)


if __name__ == "__main__":
    unittest.main()
