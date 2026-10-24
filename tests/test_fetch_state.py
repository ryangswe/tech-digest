import json
import unittest
from datetime import timedelta

from techdigest.config import parse_config
from techdigest.fetch import expand_url, mark_seen, run_fetch
from techdigest.items import Item
from techdigest.net import FetchError
from techdigest.state import Seen, SourceState

from helpers import NOW, TempDir, feed


def config(*sources, **top):
    return parse_config({"timezone": "America/Chicago", "sources": list(sources), **top})


def getter_from(mapping):
    def get(url, source_id):
        v = mapping[source_id]
        if isinstance(v, Exception):
            raise v
        return v
    return get


SIMON = {"id": "simon", "name": "Simon", "type": "feed", "url": "https://s.example/atom", "cap": 10}
HN = {"id": "hn", "name": "HN", "type": "hn", "url": "https://hn.example/?since={since:24}",
      "aggregator": True, "cap": 10}


def run(cfg, mapping, state, out, now=NOW):
    return run_fetch(cfg, state_dir=state, out_dir=out, now=now, getter=getter_from(mapping),
                     log=lambda *a: None)


def cands(out):
    return json.loads((out / "candidates.json").read_text())["candidates"]


class FetchTest(unittest.TestCase):
    def test_failing_source_is_isolated_and_reported(self):
        cfg = config(SIMON, {**HN, "id": "broken"})
        with TempDir() as d:
            report = run(cfg, {"simon": feed("simon-willison.atom"), "broken": FetchError("HTTP 429")},
                         d / "state", d / "out")
            self.assertTrue(report["sources"]["simon"]["ok"])
            self.assertEqual(report["sources"]["broken"], {"name": "HN", "ok": False, "fetched": 0,
                                                           "new": 0, "error": "HTTP 429"})
            self.assertEqual(len(cands(d / "out")), 2)  # third Simon entry is outside the window

    def test_unparseable_source_is_isolated(self):
        cfg = config(SIMON)
        with TempDir() as d:
            report = run(cfg, {"simon": b"<html>blocked"}, d / "state", d / "out")
            self.assertFalse(report["sources"]["simon"]["ok"])
            self.assertIn("XML", report["sources"]["simon"]["error"])

    def test_aggregator_merges_into_first_party_item(self):
        cfg = config(SIMON, HN)
        with TempDir() as d:
            run(cfg, {"simon": feed("simon-willison.atom"), "hn": feed("hn-front.json")}, d / "s", d / "o")
            c = [c for c in cands(d / "o") if "fixture-context" in c["url"]]
            self.assertEqual(len(c), 1)
            self.assertEqual(c[0]["source"], "simon")
            self.assertEqual(c[0]["points"], 412)
            self.assertEqual(c[0]["discussions"][0]["name"], "HN · 412 points")
            self.assertIn("hn:1000001", c[0]["keys"])

    def test_aggregator_links_named_by_site(self):
        cfg = config(HN)
        with TempDir() as d:
            run(cfg, {"hn": feed("hn-front.json")}, d / "s", d / "o")
            names = {c["url"]: c["link_name"] for c in cands(d / "o")}
            self.assertEqual(names["https://example.org/webgpu-db"], "example.org")
            self.assertEqual(names["https://news.ycombinator.com/item?id=1000003"], "HN")

    def test_seen_items_dropped_including_via_discussion_key(self):
        cfg = config(HN)
        with TempDir() as d:
            Seen({"hn:1000002": "2026-10-20"}).save(d / "s/seen.json")
            run(cfg, {"hn": feed("hn-front.json")}, d / "s", d / "o")
            self.assertNotIn("https://example.org/webgpu-db", [c["url"] for c in cands(d / "o")])

    def test_include_keywords_and_window(self):
        cfg = config({**HN, "include": ["onnx"]})
        with TempDir() as d:
            run(cfg, {"hn": feed("hn-keywords.json")}, d / "s", d / "o")
            self.assertEqual([c["title"][:7] for c in cands(d / "o")], ["Running"])
        with TempDir() as d:  # two days later, both stories are outside the 2-day default window
            run(config(HN), {"hn": feed("hn-keywords.json")}, d / "s", d / "o", now=NOW + timedelta(days=3))
            self.assertEqual(cands(d / "o"), [])

    def test_per_source_cap_prefers_points(self):
        cfg = config({**HN, "cap": 1})
        with TempDir() as d:
            run(cfg, {"hn": feed("hn-front.json")}, d / "s", d / "o")
            self.assertEqual([c["points"] for c in cands(d / "o")], [412])

    def test_global_cap_keeps_tool_sources_first(self):
        cfg = config(HN, {**SIMON, "tags": ["tool"]}, max_candidates=2)
        with TempDir() as d:
            run(cfg, {"hn": feed("hn-front.json"), "simon": feed("simon-willison.atom")}, d / "s", d / "o")
            self.assertEqual([c["source"] for c in cands(d / "o")], ["simon", "simon"])

    def test_html_links_bootstrap_then_only_new_links(self):
        s = {"id": "news", "name": "News", "type": "html_links", "url": "https://www.anthropic.com/news",
             "pattern": "^/news/[a-z0-9-]+$", "min_title_chars": 12}
        cfg = config(s)
        page1 = b'<a href="/news/first-post"><h3>The first post title</h3></a>'
        page2 = page1 + b'<a href="/news/second-post"><h3>The second post title</h3></a>'
        with TempDir() as d:
            r = run(cfg, {"news": page1}, d / "s", d / "o")
            self.assertTrue(r["sources"]["news"]["bootstrapped"])
            self.assertEqual(cands(d / "o"), [])
            run(cfg, {"news": page2}, d / "s", d / "o")
            self.assertEqual([c["title"] for c in cands(d / "o")], ["The second post title"])

    def test_html_links_does_not_bootstrap_on_an_empty_page(self):
        s = {"id": "news", "name": "News", "type": "html_links", "url": "https://www.anthropic.com/news",
             "pattern": "^/news/[a-z0-9-]+$", "min_title_chars": 12}
        cfg = config(s)
        links = b'<a href="/news/first-post"><h3>The first post title</h3></a>'
        with TempDir() as d:
            r = run(cfg, {"news": b"<html>Please verify you are human</html>"}, d / "s", d / "o")
            self.assertNotIn("bootstrapped", r["sources"]["news"])
            run(cfg, {"news": links}, d / "s", d / "o")  # first real page: baseline, not news
            self.assertEqual(cands(d / "o"), [])

    def test_page_watch_first_sight_silent_then_reports_changed_text(self):
        s = {"id": "pol", "name": "Policy", "type": "page_watch", "url": "https://p.example/policy"}
        cfg = config(s)
        v1 = b"<main><p>Rule one stays.</p><p>Rule two stays.</p><p>Rule three goes.</p></main>"
        v2 = b"<main><p>Rule one stays.</p><p>Rule two stays.</p><p>Rule four is new.</p></main>"
        with TempDir() as d:
            run(cfg, {"pol": v1}, d / "s", d / "o")
            self.assertEqual(cands(d / "o"), [])
            run(cfg, {"pol": v1}, d / "s", d / "o")
            self.assertEqual(cands(d / "o"), [])
            run(cfg, {"pol": v2}, d / "s", d / "o")
            [c] = cands(d / "o")
            self.assertEqual(c["title"], "Policy changed")
            self.assertIn("Rule four is new.", c["summary"])
            self.assertIn("1 paragraph(s) removed", c["summary"])

    def test_quiet_sources_flagged_after_three_empty_runs(self):
        cfg = config(SIMON)
        with TempDir() as d:
            for _ in range(3):
                r = run(cfg, {"simon": b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'}, d / "s", d / "o")
            self.assertEqual(r["quiet"], ["simon"])

    def test_expand_since(self):
        self.assertEqual(expand_url("x?t={since:24}", NOW), f"x?t={int(NOW.timestamp()) - 86400}")


class SeenTest(unittest.TestCase):
    def test_mark_does_not_overwrite_first_seen(self):
        s = Seen({"a": "2026-10-01"})
        s.mark(["a", "b"], "2026-10-23")
        self.assertEqual(s.items, {"a": "2026-10-01", "b": "2026-10-23"})

    def test_prune_after_60_days(self):
        s = Seen({"old": "2026-08-23", "edge": "2026-08-24", "new": "2026-10-22"})
        self.assertEqual(s.prune("2026-10-23"), 1)  # 2026-08-24 is exactly 60 days back: kept
        self.assertEqual(sorted(s.items), ["edge", "new"])

    def test_pruned_item_can_return(self):
        cfg = config({**HN, "max_age_days": 1000})
        with TempDir() as d:
            Seen({"hn:1000003": "2026-08-01"}).save(d / "s/seen.json")
            run(cfg, {"hn": feed("hn-front.json")}, d / "s", d / "o")  # seen: dropped
            self.assertNotIn("hn:1000003", [k for c in cands(d / "o") for k in c["keys"]])
            added, pruned = mark_seen(state_dir=d / "s", candidates_path=d / "o/candidates.json",
                                      today="2026-10-23")
            self.assertEqual(pruned, 1)
            run(cfg, {"hn": feed("hn-front.json")}, d / "s", d / "o")
            self.assertIn("hn:1000003", [k for c in cands(d / "o") for k in c["keys"]])

    def test_mark_seen_covers_all_candidates_and_saves_sorted(self):
        cfg = config(HN)
        with TempDir() as d:
            run(cfg, {"hn": feed("hn-front.json")}, d / "s", d / "o")
            added, _ = mark_seen(state_dir=d / "s", candidates_path=d / "o/candidates.json",
                                 today="2026-10-23")
            self.assertEqual(added, 5)  # 2 link stories x (URL + HN thread) + 1 Ask HN thread
            text = (d / "s/seen.json").read_text()
            keys = list(json.loads(text)["items"])
            self.assertEqual(keys, sorted(keys))
            run(cfg, {"hn": feed("hn-front.json")}, d / "s", d / "o")
            self.assertEqual(cands(d / "o"), [])

    def test_union_keeps_earliest(self):
        u = Seen({"a": "2026-10-05", "b": "2026-10-01"}).union(Seen({"a": "2026-10-02", "c": "2026-10-09"}))
        self.assertEqual(u.items, {"a": "2026-10-02", "b": "2026-10-01", "c": "2026-10-09"})

    def test_source_state_merge_newer_wins(self):
        a = SourceState({"sources": {"x": {"fail_days": 2}, "y": {"fail_days": 0}}})
        b = SourceState({"sources": {"x": {"fail_days": 0}}})
        self.assertEqual(a.merged_with(b).data["sources"], {"x": {"fail_days": 0}, "y": {"fail_days": 0}})


class ItemTest(unittest.TestCase):
    def test_id_stable_from_key(self):
        a = Item("s", "t", "https://www.e.com/x/?utm_source=a")
        b = Item("s", "t", "http://e.com/x")
        self.assertEqual(a.id, b.id)
        self.assertEqual(len(a.id), 10)


if __name__ == "__main__":
    unittest.main()
