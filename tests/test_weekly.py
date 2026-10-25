import json
import unittest

from techdigest import weekly
from techdigest.feedback import append_lines, load_lines

from helpers import TempDir
from test_deliver import FakeGitHub

MONDAY = "2026-10-26"  # ISO week 2026-W44


def card(i, kind="try", effort="1h", confidence="high", **kw):
    return {"id": f"{i:010x}", "kind": kind, "effort": effort, "confidence": confidence,
            "fits": ["workflow kit"], "what": f"What {i}.", "why_you": f"Why {i}.",
            "next_step": f"Step {i}.", "flags": [], "title": f"Card {i}",
            "url": f"https://example.com/{i}", "source_name": "News", "source": "news", **kw}


def write_digest_cards(repo, day, cards):
    p = repo / f"digest/{day}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"date": day, "cards": cards}))


class BuildTest(unittest.TestCase):
    def test_week_id(self):
        self.assertEqual(weekly.week_id(weekly.date(2026, 10, 26)), "2026-W44")

    def test_ranks_votes_and_asks_first_and_drops_rejected(self):
        with TempDir() as repo:
            write_digest_cards(repo, "2026-10-20", [card(1, kind="watch"), card(2), card(3)])
            write_digest_cards(repo, "2026-10-25", [card(4, effort="15m"), card(5)])
            write_digest_cards(repo, "2026-10-26", [card(9)])  # today's: next week's batch
            append_lines(repo / "state/feedback.jsonl", [
                {"digest": "2026-10-20", "kind": "vote", "vote": 1, "id": card(1)["id"]},
                {"digest": "2026-10-20", "kind": "vote", "vote": -1, "id": card(2)["id"]},
                {"digest": "2026-10-25", "kind": "dig", "id": card(5)["id"]},
            ])
            w = weekly.build(repo, MONDAY)
        ids = [c["id"] for c in w["cards"]]
        self.assertEqual(set(ids[:2]), {card(1)["id"], card(5)["id"]})  # 👍 and 🔍 lead
        self.assertNotIn(card(2)["id"], ids)                        # 👎 dropped
        self.assertNotIn(card(9)["id"], ids)                        # not last week's
        self.assertEqual(w["week"], "2026-W44")

    def test_backlog_mix_and_cap(self):
        with TempDir() as repo:
            write_digest_cards(repo, "2026-10-21", [card(i) for i in range(1, 12)])
            q = [{**card(100 + i), "status": "queued"} for i in range(8)]
            (repo / "backlog").mkdir()
            (repo / "backlog/queue.json").write_text(json.dumps(q))
            w = weekly.build(repo, MONDAY)
        self.assertEqual(len(w["cards"]), 10)
        self.assertEqual(len(w["backlog_ids"]), 5)
        self.assertEqual(w["backlog_left"], 3)
        self.assertEqual(w["cards"][-1]["from"], "your bookmarks")

    def test_week_fills_when_backlog_is_empty(self):
        with TempDir() as repo:
            write_digest_cards(repo, "2026-10-21", [card(i) for i in range(1, 15)])
            self.assertEqual(len(weekly.build(repo, MONDAY)["cards"]), 10)

    def test_empty_week(self):
        with TempDir() as repo:
            self.assertIsNone(weekly.build(repo, MONDAY))

    def test_later_comes_back_once_and_done_never(self):
        with TempDir() as repo:
            (repo / "reviews").mkdir()
            (repo / "reviews/2026-W43.json").write_text(json.dumps({"cards": [card(1), card(2), card(3)]}))
            append_lines(repo / "state/feedback.jsonl", [
                {"digest": "2026-W43", "kind": "later", "id": card(1)["id"], "harvested": MONDAY},
                {"digest": "2026-W43", "kind": "tried", "id": card(2)["id"], "harvested": MONDAY},
            ])
            write_digest_cards(repo, "2026-10-22", [card(2), card(3), card(4)])
            w = weekly.build(repo, MONDAY)
            ids = {c["id"] for c in w["cards"]}
            self.assertEqual(ids, {card(1)["id"], card(4)["id"]})  # 3 was shown already; 2 is done
            (repo / "reviews/2026-W44.json").write_text(json.dumps(w))
            w2 = weekly.build(repo, "2026-11-02")
        self.assertIsNone(w2)  # "later" from W43 does not come back a second time


class IssueTest(unittest.TestCase):
    def test_prepare_publish_harvest_cycle(self):
        gh = FakeGitHub()
        with TempDir() as repo:
            write_digest_cards(repo, "2026-10-21", [card(1), card(2)])
            q = [{**card(100), "status": "queued"}]
            (repo / "backlog").mkdir()
            (repo / "backlog/queue.json").write_text(json.dumps(q))
            self.assertEqual(weekly.prepare(gh, repo, "2026-10-27"), {"skipped": "not Monday"})
            r = weekly.prepare(gh, repo, MONDAY)
            self.assertTrue(r["built"])
            self.assertEqual(json.loads((repo / "backlog/queue.json").read_text())[0]["status"], "shown")
            self.assertEqual(weekly.prepare(gh, repo, MONDAY)["built"], False)  # idempotent
            self.assertEqual(weekly.publish(gh, repo, MONDAY)["created"], 1)
            self.assertIsNone(weekly.publish(gh, repo, MONDAY)["created"])
            md = gh.issues[0]["body"]
            self.assertIn("<!-- try-this:2026-W44 -->", md)
            self.assertEqual(md.count("- [ ] ✅ Done"), 3)
            # the owner ticks, a week passes
            cid = card(1)["id"]
            gh.issues[0]["body"] = md.replace(f"- [ ] 🙅 Not for me <!-- card:{cid} -->",
                                              f"- [x] 🙅 Not for me <!-- card:{cid} -->")
            write_digest_cards(repo, "2026-10-28", [card(1), card(5)])
            weekly.prepare(gh, repo, "2026-11-02")
            kinds = [(ln["kind"], ln.get("id")) for ln in load_lines(repo / "state/feedback.jsonl")]
            self.assertIn(("not_for_me", cid), kinds)
            nxt = json.loads((repo / "reviews/2026-W45.json").read_text())
            self.assertEqual([c["id"] for c in nxt["cards"]], [card(5)["id"]])
            self.assertEqual(weekly.publish(gh, repo, "2026-11-02"), {"created": 2, "closed": [1]})
            weekly.prepare(gh, repo, "2026-11-02")  # re-run: no duplicate harvest
            self.assertEqual(sum(1 for k, _ in kinds if k == "not_for_me"),
                             sum(1 for ln in load_lines(repo / "state/feedback.jsonl") if ln["kind"] == "not_for_me"))

    def test_last_box_wins(self):
        body = ("- [x] ⏳ Later <!-- card:aaaaaaaaaa -->\n- [x] ✅ Done <!-- card:aaaaaaaaaa -->")
        self.assertEqual(weekly.parse_ticks(body), [("tried", "aaaaaaaaaa")])


if __name__ == "__main__":
    unittest.main()
