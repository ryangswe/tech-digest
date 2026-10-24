import json
import unittest

from techdigest import deliver
from techdigest.feedback import load_lines, parse_ticks
from techdigest.render import build_digest, to_markdown, write_digest

from helpers import TempDir, candidates_doc, good_picks

OWNER = "ryangswe"


class FakeGitHub:
    def __init__(self):
        self.issues: list[dict] = []
        self.reactions: dict[int, list] = {}
        self.comments: dict[int, list] = {}
        self.pulls: list[dict] = []
        self.labels: set[str] = set()
        self.calls: list[tuple] = []

    def list_issues(self, label, state="open"):
        return [i for i in self.issues if label in i["labels"] and (state == "all" or i["state"] == state)]

    def create_issue(self, title, body, labels):
        n = len(self.issues) + 1
        self.issues.append({"number": n, "title": title, "body": body, "labels": labels, "state": "open"})
        self.calls.append(("create", n))
        return {"number": n}

    def close_issue(self, number):
        self.issues[number - 1]["state"] = "closed"
        self.calls.append(("close", number))

    def issue_reactions(self, n):
        return self.reactions.get(n, [])

    def issue_comments(self, n):
        return self.comments.get(n, [])

    def open_pulls(self):
        return self.pulls

    def ensure_label(self, name, color, description):
        self.labels.add(name)


def make_day(root, day):
    doc = candidates_doc(day=day)
    d = build_digest(good_picks(doc), doc)
    write_digest(d, root / "digest")
    return d


class DeliverTest(unittest.TestCase):
    def test_publish_is_idempotent_and_closes_earlier_digest(self):
        gh = FakeGitHub()
        with TempDir() as root:
            make_day(root, "2026-10-22")
            make_day(root, "2026-10-23")
            deliver.publish(gh, root, "2026-10-22")
            r = deliver.publish(gh, root, "2026-10-23")
            self.assertEqual(r, {"created": 2, "closed": [1]})
            self.assertEqual(deliver.publish(gh, root, "2026-10-23"), {"created": None, "closed": []})
            self.assertEqual([i["state"] for i in gh.issues], ["closed", "open"])
            self.assertEqual(gh.issues[1]["title"], "☕ Tech Digest — Fri 23 Oct 2026")
            self.assertIn("<!-- digest:2026-10-23 -->", gh.issues[1]["body"])
            self.assertIn("digest", gh.labels)

    def test_publish_links_waiting_interests_prs(self):
        gh = FakeGitHub()
        gh.pulls = [{"number": 7, "title": "Tune interests", "html_url": "https://github.com/x/pull/7",
                     "head": {"ref": "claude/interests-2026-10-19"}},
                    {"number": 8, "title": "Other", "html_url": "u", "head": {"ref": "feature"}}]
        with TempDir() as root:
            make_day(root, "2026-10-23")
            deliver.publish(gh, root, "2026-10-23")
            body = gh.issues[0]["body"]
            self.assertIn("[#7 Tune interests](https://github.com/x/pull/7)", body)
            self.assertNotIn("#8", body)

    def test_harvest_ticks_reactions_and_owner_comments_once(self):
        gh = FakeGitHub()
        with TempDir() as root:
            d = make_day(root, "2026-10-22")
            make_day(root, "2026-10-23")
            deliver.publish(gh, root, "2026-10-22")
            body = gh.issues[0]["body"]
            top_id, skim_id = d["top"][0]["id"], d["skim"][0]["id"]
            body = body.replace(f"- [ ] 👍 Headline 1 <!-- id:{top_id} -->", f"- [x] 👍 Headline 1 <!-- id:{top_id} -->")
            body = body.replace(f"- [ ] 👎 News: Item 3 title <!-- id:{skim_id} -->",
                                f"- [x] 👎 News: Item 3 title <!-- id:{skim_id} -->")
            gh.issues[0]["body"] = body
            gh.reactions[1] = [{"content": "+1", "user": {"login": OWNER}},
                               {"content": "+1", "user": {"login": "someone-else"}},
                               {"content": "heart", "user": {"login": OWNER}}]
            gh.comments[1] = [{"body": "More like #1 please", "user": {"login": OWNER}},
                              {"body": "spam", "user": {"login": "bot"}}]
            lines = deliver.harvest(gh, root, OWNER, "2026-10-23")
            kinds = [(ln["kind"], ln.get("vote"), ln.get("id")) for ln in lines]
            self.assertIn(("vote", 1, top_id), kinds)
            self.assertIn(("vote", -1, skim_id), kinds)
            self.assertIn(("reaction", 1, None), kinds)
            self.assertEqual([ln["text"] for ln in lines if ln["kind"] == "comment"], ["More like #1 please"])
            vote = next(ln for ln in lines if ln.get("id") == top_id)
            self.assertEqual((vote["title"], vote["source"], vote["digest"]), ("Headline 1", "news", "2026-10-22"))
            # a re-run (say the close failed) does not duplicate
            self.assertEqual(deliver.harvest(gh, root, OWNER, "2026-10-23"), [])
            self.assertEqual(len(load_lines(root / "state/feedback.jsonl")), len(lines))

    def test_harvest_skips_todays_issue(self):
        gh = FakeGitHub()
        with TempDir() as root:
            make_day(root, "2026-10-23")
            deliver.publish(gh, root, "2026-10-23")
            self.assertEqual(deliver.harvest(gh, root, OWNER, "2026-10-23"), [])

    def test_failure_issue_opened_once(self):
        gh = FakeGitHub()
        self.assertEqual(deliver.report_failure(gh, "Digest run failed", "log"), 1)
        self.assertIsNone(deliver.report_failure(gh, "Digest run failed", "log"))

    def test_check_delivered(self):
        gh = FakeGitHub()
        with TempDir() as root:
            self.assertEqual(deliver.check_delivered(gh, root, "2026-10-23"), 1)
            self.assertIn("No digest today (2026-10-23)", gh.issues[0]["title"])
            make_day(root, "2026-10-24")
            self.assertIsNone(deliver.check_delivered(gh, root, "2026-10-24"))


class TickParseTest(unittest.TestCase):
    def test_both_ticked_cancels(self):
        body = ("- [x] 👍 A <!-- id:aaaaaaaaaa -->\n- [x] 👎 A <!-- id:aaaaaaaaaa -->\n"
                "- [X] 👍 B <!-- id:bbbbbbbbbb -->\n- [ ] 👎 B <!-- id:bbbbbbbbbb -->")
        self.assertEqual(parse_ticks(body), [(1, "bbbbbbbbbb")])

    def test_rendered_digest_boxes_parse_once_ticked(self):
        doc = candidates_doc()
        md = to_markdown(build_digest(good_picks(doc), doc))
        self.assertEqual(parse_ticks(md), [])
        self.assertEqual(len(parse_ticks(md.replace("- [ ] 👍", "- [x] 👍"))),
                         len(json.loads(json.dumps(good_picks(doc)))["top"]) + 5 + 2)


if __name__ == "__main__":
    unittest.main()
