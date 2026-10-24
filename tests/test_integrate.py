import json
import shutil
import subprocess
import unittest

from techdigest.integrate import IntegrateError, integrate
from techdigest.render import build_digest, to_markdown, write_digest

from helpers import TempDir, candidates_doc, good_picks

DAY = "2026-10-23"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class IntegrateTest(unittest.TestCase):
    """A bare origin, a 'cloud' clone that pushes a digest branch, and a 'main' clone that integrates."""

    def setUp(self):
        self.tmp = TempDir()
        d = self.tmp.__enter__()
        self.origin, self.cloud, self.main = d / "origin.git", d / "cloud", d / "main"
        git(d, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(d, "clone", "-q", str(self.origin), str(self.cloud))
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            git(self.cloud, "config", k, v)
        (self.cloud / "state").mkdir()
        (self.cloud / "state/seen.json").write_text(json.dumps(
            {"version": 1, "items": {"a": "2026-10-01", "old": "2026-07-01"}}))
        (self.cloud / "README.md").write_text("code\n")
        git(self.cloud, "add", "-A")
        git(self.cloud, "commit", "-qm", "base")
        git(self.cloud, "push", "-q", "origin", "main")
        git(d, "clone", "-q", str(self.origin), str(self.main))
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            git(self.main, "config", k, v)

    def tearDown(self):
        self.tmp.__exit__(None, None, None)

    def push_branch(self, extra=None, tamper_md=False, seen=None):
        git(self.cloud, "checkout", "-qb", f"claude/digest-{DAY}")
        doc = candidates_doc()
        write_digest(build_digest(good_picks(doc), doc), self.cloud / "digest")
        if tamper_md:
            p = self.cloud / f"digest/{DAY}.md"
            p.write_text(p.read_text() + "\nInjected text\n")
        (self.cloud / "state/seen.json").write_text(json.dumps(
            {"version": 1, "items": seen or {"a": "2026-10-01", "b": DAY}}))
        for path, text in (extra or {}).items():
            (self.cloud / path).write_text(text)
        git(self.cloud, "add", "-A")
        git(self.cloud, "commit", "-qm", "digest")
        git(self.cloud, "push", "-q", "origin", f"claude/digest-{DAY}")
        git(self.main, "fetch", "-q", "origin")

    def test_copies_digest_and_unions_seen(self):
        self.push_branch()
        # main moved on meanwhile: a commit added another seen key there
        (self.main / "state/seen.json").write_text(json.dumps(
            {"version": 1, "items": {"a": "2026-10-01", "c": "2026-10-22", "old": "2026-07-01"}}))
        git(self.main, "commit", "-qam", "main moved")
        git(self.main, "push", "-q", "origin", "HEAD:main")
        git(self.main, "fetch", "-q", "origin")
        result = integrate(self.main, f"claude/digest-{DAY}")
        self.assertEqual(result["paths"], [f"digest/{DAY}.json", f"digest/{DAY}.md", "state/seen.json"])
        items = json.loads((self.main / "state/seen.json").read_text())["items"]
        self.assertEqual(items, {"a": "2026-10-01", "b": DAY, "c": "2026-10-22"})  # "old" pruned
        self.assertTrue((self.main / f"digest/{DAY}.md").exists())

    def test_refuses_other_paths(self):
        self.push_branch(extra={"README.md": "hacked\n"})
        with self.assertRaises(IntegrateError) as e:
            integrate(self.main, f"claude/digest-{DAY}")
        self.assertIn("M README.md", str(e.exception))
        self.assertFalse((self.main / f"digest/{DAY}.md").exists())

    def test_refuses_another_days_digest(self):
        self.push_branch(extra={"digest/2026-10-01.md": "backdated\n"})
        with self.assertRaises(IntegrateError):
            integrate(self.main, f"claude/digest-{DAY}")

    def test_markdown_is_always_rerendered_from_json(self):
        self.push_branch(tamper_md=True)
        integrate(self.main, f"claude/digest-{DAY}")
        md = (self.main / f"digest/{DAY}.md").read_text()
        self.assertNotIn("Injected text", md)
        self.assertEqual(md, to_markdown(json.loads((self.main / f"digest/{DAY}.json").read_text())))

    def deliver_to_main(self):
        """What the workflow does after integrate: commit on main and push."""
        git(self.main, "add", "-A")
        git(self.main, "commit", "-qm", "digest")
        git(self.main, "push", "-q", "origin", "HEAD:main")

    def test_rerun_after_delivery_is_idempotent(self):
        self.push_branch()
        integrate(self.main, f"claude/digest-{DAY}")
        self.deliver_to_main()
        git(self.main, "fetch", "-q", "origin")
        result = integrate(self.main, f"claude/digest-{DAY}")  # e.g. publish failed, workflow re-run
        self.assertEqual(result["date"], DAY)
        status = subprocess.run(["git", "-C", str(self.main), "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertEqual(status, "")

    def test_second_run_same_day_cannot_replace_delivered_digest(self):
        self.push_branch()
        integrate(self.main, f"claude/digest-{DAY}")
        self.deliver_to_main()
        git(self.cloud, "push", "-q", "origin", "--delete", f"claude/digest-{DAY}")
        # a later run clones main (with today's digest) and pushes a new branch for the same day
        git(self.cloud, "checkout", "-q", "main")
        git(self.cloud, "branch", "-qD", f"claude/digest-{DAY}")
        git(self.cloud, "pull", "-q", "origin", "main")
        self.push_branch()
        with self.assertRaises(IntegrateError) as e:
            integrate(self.main, f"claude/digest-{DAY}")
        self.assertIn("already delivered", str(e.exception))

    def test_refuses_deletions(self):
        git(self.cloud, "checkout", "-qb", f"claude/digest-{DAY}")
        git(self.cloud, "rm", "-q", "state/seen.json")
        doc = candidates_doc()
        write_digest(build_digest(good_picks(doc), doc), self.cloud / "digest")
        git(self.cloud, "add", "-A")
        git(self.cloud, "commit", "-qm", "digest")
        git(self.cloud, "push", "-q", "origin", f"claude/digest-{DAY}")
        git(self.main, "fetch", "-q", "origin")
        with self.assertRaises(IntegrateError) as e:
            integrate(self.main, f"claude/digest-{DAY}")
        self.assertIn("D state/seen.json", str(e.exception))

    def test_refuses_stale_branch(self):
        (self.main / "digest").mkdir()
        (self.main / "digest/2026-10-25.json").write_text("{}")
        self.push_branch()
        with self.assertRaises(IntegrateError) as e:
            integrate(self.main, f"claude/digest-{DAY}")
        self.assertIn("stale branch", str(e.exception))

    def test_state_merges_never_go_backwards(self):
        (self.main / "state/weekly.json").write_text(json.dumps({"last_proposal": "2026-10-19"}))
        (self.main / "state/sources.json").write_text(json.dumps(
            {"sources": {"only-main": {"last_ok": "2026-10-22"}}}))
        self.push_branch(extra={"state/weekly.json": json.dumps({"last_proposal": "2026-10-12"}),
                                "state/sources.json": json.dumps({"sources": {"hn": {"last_ok": DAY}}})})
        integrate(self.main, f"claude/digest-{DAY}")
        self.assertEqual(json.loads((self.main / "state/weekly.json").read_text()),
                         {"last_proposal": "2026-10-19"})
        self.assertEqual(sorted(json.loads((self.main / "state/sources.json").read_text())["sources"]),
                         ["hn", "only-main"])

    def test_refuses_bad_branch_name(self):
        with self.assertRaises(IntegrateError):
            integrate(self.main, "claude/something-else")


if __name__ == "__main__":
    unittest.main()
