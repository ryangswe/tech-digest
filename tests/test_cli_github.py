import io
import json
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

from techdigest.__main__ import main
from techdigest.github import GitHub, GitHubError

from helpers import ROOT, TempDir


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class GitHubClientTest(unittest.TestCase):
    def setUp(self):
        self.gh = GitHub(repo="o/r", token="t")
        self.sent = []

    def respond(self, payload):
        def urlopen(req, timeout=None):
            self.sent.append(req)
            return FakeResponse(json.dumps(payload).encode())
        return mock.patch("urllib.request.urlopen", side_effect=urlopen)

    def test_list_issues_builds_query_and_drops_pull_requests(self):
        with self.respond([{"number": 1}, {"number": 2, "pull_request": {}}]):
            out = self.gh.list_issues("digest", "all")
        self.assertEqual(out, [{"number": 1}])
        req = self.sent[0]
        self.assertEqual(req.full_url, "https://api.github.com/repos/o/r/issues?labels=digest&state=all&per_page=100")
        self.assertEqual(req.get_header("Authorization"), "Bearer t")

    def test_create_issue_posts_json(self):
        with self.respond({"number": 5}):
            self.assertEqual(self.gh.create_issue("T", "B", ["digest"])["number"], 5)
        req = self.sent[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(json.loads(req.data), {"title": "T", "body": "B", "labels": ["digest"]})

    def test_close_issue(self):
        with self.respond({}):
            self.gh.close_issue(3)
        self.assertEqual((self.sent[0].get_method(), json.loads(self.sent[0].data)["state"]), ("PATCH", "closed"))

    def test_http_error_raised_with_status(self):
        err = urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b'{"message":"no"}'))
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(GitHubError) as e:
                self.gh.list_issues("digest")
        self.assertEqual(e.exception.status, 403)

    def test_ensure_label_creates_only_when_missing(self):
        calls = []

        def urlopen(req, timeout=None):
            calls.append(req.get_method())
            if req.get_method() == "GET":
                raise urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO(b"{}"))
            return FakeResponse(b"{}")
        with mock.patch("urllib.request.urlopen", side_effect=urlopen):
            self.gh.ensure_label("digest", "fff", "d")
        self.assertEqual(calls, ["GET", "POST"])


class ReadCardsDigCliTest(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        from contextlib import redirect_stderr
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--config", str(ROOT / "sources.json"), *args])
        return code, out.getvalue(), err.getvalue()

    def test_read_then_cards_offline(self):
        with TempDir() as d:
            cands = {"date": "2026-10-24", "candidates": [
                {"id": "00000000aa", "url": "https://example.org/blog/fresh-reviewer", "title": "T",
                 "source": "s", "source_name": "S", "summary": ""}]}
            (d / "c.json").write_text(json.dumps(cands))
            code, out, _ = self.run_cli("read", "--ids", "00000000aa", "--candidates", str(d / "c.json"),
                                        "--out", str(d / "reads"), "--fixtures", str(ROOT / "fixtures/reads"))
            self.assertEqual(code, 0)
            self.assertIn("read 1/1 ok", out)
            self.assertNotIn("Splitting a reviewer", out)  # no page text in what the session sees
            (d / "cards").mkdir()
            (d / "cards/00000000aa.json").write_text(json.dumps({
                "id": "00000000aa", "kind": "try", "effort": "1h", "fits": ["workflow kit"],
                "confidence": "high", "what": "W.", "why_you": "Y.", "next_step": "S.",
                "flags": ["page addressed agents"]}))
            code, out, err = self.run_cli("cards", "--reads", str(d / "reads"), "--cards-dir", str(d / "cards"),
                                          "--profile", str(ROOT / "profile.md"), "--out", str(d / "cards.json"))
            self.assertEqual((code, err), (0, ""))
            [card] = json.loads((d / "cards.json").read_text())
            self.assertIs(card["flagged"], True)
            self.assertEqual(card["url"], "https://example.org/blog/fresh-reviewer")

    def test_read_unknown_id(self):
        with TempDir() as d:
            (d / "c.json").write_text(json.dumps({"date": "x", "candidates": []}))
            self.assertEqual(self.run_cli("read", "--ids", "ffffffffff", "--candidates", str(d / "c.json"))[0], 2)

    def test_dig_requests_without_gh_writes_empty_list(self):
        with TempDir() as d, mock.patch("subprocess.run", side_effect=FileNotFoundError("gh")):
            code, _, err = self.run_cli("dig-requests", "--out", str(d / "dig.json"))
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((d / "dig.json").read_text()), [])
            self.assertIn("unavailable", err)


class StatusCliTest(unittest.TestCase):
    def status(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main(["--config", str(ROOT / "sources.json"), "status", *args]), 0)
        return json.loads(buf.getvalue())

    def test_status_contract(self):
        with TempDir() as d:
            out = self.status("--state", str(d), "--digest-dir", str(d), "--now", "2026-10-23T11:30:00Z")
        self.assertEqual(out["date"], "2026-10-23")
        self.assertEqual(out["branch"], "claude/digest-2026-10-23")
        self.assertIs(out["already_delivered"], False)
        self.assertIn("weekly_review_due", out)

    def test_already_delivered(self):
        with TempDir() as d:
            (d / "2026-10-23.md").write_text("x")
            out = self.status("--state", str(d), "--digest-dir", str(d), "--date", "2026-10-23")
        self.assertIs(out["already_delivered"], True)
        self.assertIs(out["weekly_review_due"], False)


if __name__ == "__main__":
    unittest.main()
