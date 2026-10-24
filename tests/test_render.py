import copy
import re
import unittest

from techdigest.picks import validate_picks
from techdigest.rank_keywords import keyword_picks
from techdigest.render import RenderError, build_digest, to_markdown, validate_digest

from helpers import candidates_doc, good_picks

REPORT = {"sources": {"news": {"name": "News", "ok": True}, "tools": {"name": "Tool releases", "ok": True},
                      "reddit": {"name": "Reddit", "ok": False, "error": "HTTP 429"},
                      "yt1": {"name": "YT one", "ok": False, "error": "HTTP 404"},
                      "yt2": {"name": "YT two", "ok": False, "error": "HTTP 404"}},
          "quiet": ["optcg-news"]}


class PicksValidationTest(unittest.TestCase):
    def setUp(self):
        self.doc = candidates_doc()
        self.picks = good_picks(self.doc)

    def errors(self, mutate):
        p = copy.deepcopy(self.picks)
        mutate(p)
        return "\n".join(validate_picks(p, self.doc))

    def test_good_picks_pass(self):
        self.assertEqual(validate_picks(self.picks, self.doc), [])

    def test_unknown_id(self):
        self.assertIn("not a candidate id", self.errors(lambda p: p["skim"][0].update(id="nope")))

    def test_repeated_id(self):
        self.assertIn("already used", self.errors(lambda p: p["skim"][0].update(id=p["top"][0]["id"])))

    def test_url_in_text(self):
        for bad in ("See https://example.com", "at www.example.com", "[x](y)", "example.com/path"):
            with self.subTest(bad=bad):
                self.assertIn("URL", self.errors(lambda p: p["top"][0].update(why=bad)))

    def test_html_and_line_breaks(self):
        self.assertIn("no HTML", self.errors(lambda p: p["skim"][0].update(line="a <b>b</b>")))
        self.assertIn("no HTML", self.errors(lambda p: p["skim"][0].update(line="a\nb")))

    def test_markdown_block_syntax(self):
        self.assertIn("plain prose", self.errors(lambda p: p.update(opener="# Hello")))

    def test_top_must_have_exactly_three(self):
        self.assertIn("exactly 3", self.errors(lambda p: p["top"].pop()))

    def test_top_count_follows_small_candidate_lists(self):
        doc = candidates_doc(n_tools=0, n_other=2)
        picks = good_picks(doc)
        self.assertEqual(len(picks["top"]), 2)
        self.assertEqual(validate_picks(picks, doc), [])

    def test_empty_day_needs_only_an_opener(self):
        doc = {"date": "2026-10-23", "candidates": []}
        picks = {"date": "2026-10-23", "opener": "Quiet one today.", "top": [], "skim": [], "tools": []}
        self.assertEqual(validate_picks(picks, doc), [])

    def test_section_limits(self):
        doc = candidates_doc(n_tools=8, n_other=20)
        picks = good_picks(doc)
        ids = [c["id"] for c in doc["candidates"] if "tool" not in c["tags"]]
        picks["skim"] = [{"id": i, "line": "x"} for i in ids[3:14]]
        msgs = "\n".join(validate_picks(picks, doc))
        self.assertIn("skim: at most 10", msgs)
        self.assertIn("tools: at most 6", msgs)

    def test_tools_only_from_tool_sources(self):
        self.assertIn("not from a `tool` source",
                      self.errors(lambda p: p["tools"].append({"id": p["skim"].pop()["id"], "line": "x"})))

    def test_word_limits_and_total_budget(self):
        self.assertIn("14-word limit", self.errors(lambda p: p["top"][0].update(headline="word " * 15)))

        # Every field just under its own limit, every section full: over the total budget.
        doc = candidates_doc(n_tools=6, n_other=13)
        p = good_picks(doc)
        for e in p["top"]:
            e.update(headline="word " * 14, summary="word " * 80, why="word " * 50)
        p["skim"] = [{"id": c["id"], "line": "word " * 40} for c in doc["candidates"][3:13]]
        p["tools"] = [{"id": c["id"], "line": "word " * 40} for c in doc["candidates"][13:]]
        p["opener"] = "word " * 40
        msgs = "\n".join(validate_picks(p, doc))
        self.assertIn("5-minute", msgs)
        self.assertNotIn("-word limit", msgs)

    def test_date_and_unknown_fields(self):
        self.assertIn("date: must be", self.errors(lambda p: p.update(date="2026-10-22")))
        self.assertIn("unknown field", self.errors(lambda p: p.update(extra=1)))
        self.assertIn("unknown field", self.errors(lambda p: p["top"][0].update(url="x")))


class DigestFormatTest(unittest.TestCase):
    def setUp(self):
        self.doc = candidates_doc()
        self.doc["candidates"][0]["discussions"] = [
            {"name": "HN · 412 points", "url": "https://news.ycombinator.com/item?id=1", "comments": 230}]
        self.digest = build_digest(good_picks(self.doc), self.doc, REPORT)
        self.md = to_markdown(self.digest)

    def test_sections_in_order(self):
        heads = re.findall(r"^## (.+)$", self.md, re.M)
        self.assertEqual(heads, ["🏆 Top 3", "👀 Worth a skim", "🔧 Changed in my tools"])
        self.assertTrue(self.md.startswith("# ☕ Tech Digest — Fri 23 Oct 2026\n"))
        self.assertEqual(len(re.findall(r"^### \d\. ", self.md, re.M)), 3)
        self.assertEqual(self.md.count("**Why it matters to you:**"), 3)

    def test_every_item_links_to_its_source(self):
        for section in ("top", "skim", "tools"):
            for e in self.digest[section]:
                self.assertIn(f"]({e['url']})", self.md, e["id"])

    def test_discussion_links_rendered(self):
        self.assertIn("[HN · 412 points, 230 comments](https://news.ycombinator.com/item?id=1)", self.md)

    def test_feedback_box_pair_per_item(self):
        n = sum(len(self.digest[s]) for s in ("top", "skim", "tools"))
        self.assertEqual(len(re.findall(r"^- \[ \] 👍 .+ <!-- id:[0-9a-f]{10} -->$", self.md, re.M)), n)
        self.assertEqual(len(re.findall(r"^- \[ \] 👎 .+ <!-- id:[0-9a-f]{10} -->$", self.md, re.M)), n)

    def test_footer_groups_failures_and_lists_quiet_sources(self):
        foot = self.md.strip().splitlines()[-1]
        self.assertIn("failed today: Reddit (HTTP 429); YT one, YT two (HTTP 404)", foot)
        self.assertIn("no items for 3+ runs: optcg-news", foot)
        self.assertIn("ranked by Claude", foot)

    def test_empty_tools_and_quiet_day(self):
        doc = {"date": "2026-10-23", "candidates": []}
        d = build_digest({"date": "2026-10-23", "opener": "Quiet.", "top": [], "skim": [], "tools": []}, doc)
        md = to_markdown(d)
        self.assertIn("Nothing changed in your tools today.", md)
        self.assertIn("A quiet day", md)
        self.assertNotIn("<details>", md)

    def test_markdown_in_source_titles_escaped(self):
        doc = candidates_doc()
        doc["candidates"][5]["title"] = "A [bracketed] *title*"
        doc["candidates"][5]["source_name"] = doc["candidates"][5]["link_name"] = "Src [x]"
        md = to_markdown(build_digest(good_picks(doc), doc))
        self.assertIn(r"[Src \[x\]](https://example.com/5)", md)

    def test_json_is_self_contained_and_valid(self):
        self.assertEqual(validate_digest(self.digest), [])
        self.assertEqual(self.digest["schema_version"], 1)
        self.assertEqual(to_markdown(self.digest), self.md)  # deterministic re-render

    def test_build_refuses_bad_picks(self):
        bad = good_picks(self.doc)
        bad["top"][0]["why"] = "see https://x.com"
        with self.assertRaises(RenderError):
            build_digest(bad, self.doc)


class KeywordRankerTest(unittest.TestCase):
    def test_produces_valid_picks(self):
        doc = candidates_doc()
        doc["candidates"][7]["title"] = "Claude Code subagents get faster"
        picks = keyword_picks(doc, [{"term": "claude code", "weight": 5}])
        self.assertEqual(validate_picks(picks, doc), [])
        self.assertEqual(picks["top"][0]["id"], doc["candidates"][7]["id"])

    def test_strips_urls_from_source_text(self):
        doc = candidates_doc()
        for c in doc["candidates"]:
            c["summary"] = "See https://example.com/x and www.example.org for more"
        self.assertEqual(validate_picks(keyword_picks(doc, []), doc), [])


if __name__ == "__main__":
    unittest.main()
