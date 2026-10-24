import json
import shutil
import subprocess
import unittest

from techdigest.integrate import IntegrateError, integrate
from techdigest.render import build_digest, write_digest

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
        # main moved on meanwhile: another key was added there
        (self.main / "state/seen.json").write_text(json.dumps(
            {"version": 1, "items": {"a": "2026-10-01", "c": "2026-10-22", "old": "2026-07-01"}}))
        self.push_branch()
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

    def test_refuses_markdown_that_does_not_match_json(self):
        self.push_branch(tamper_md=True)
        with self.assertRaises(IntegrateError) as e:
            integrate(self.main, f"claude/digest-{DAY}")
        self.assertIn("does not match a fresh render", str(e.exception))

    def test_refuses_bad_branch_name(self):
        with self.assertRaises(IntegrateError):
            integrate(self.main, "claude/something-else")


if __name__ == "__main__":
    unittest.main()
