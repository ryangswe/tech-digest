import json
import shutil
import subprocess
import unittest

from techdigest.scope import check, snapshot

from helpers import ROOT, TempDir

HOOK = ROOT / ".claude/hooks/guard-run-scope.py"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class RunScopeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.repo = self.tmp.__enter__()
        git(self.repo, "init", "-q", "-b", "main")
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            git(self.repo, "config", k, v)
        (self.repo / ".claude/hooks").mkdir(parents=True)
        shutil.copy(HOOK, self.repo / ".claude/hooks/guard-run-scope.py")
        (self.repo / ".gitignore").write_text("build/\nbacklog/raw/\n")
        (self.repo / "techdigest").mkdir()
        (self.repo / "techdigest/render.py").write_text("x = 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")

    def tearDown(self):
        self.tmp.__exit__(None, None, None)

    def hook(self, path):
        r = subprocess.run(["python3", str(self.repo / ".claude/hooks/guard-run-scope.py")],
                           input=json.dumps({"tool_input": {"file_path": str(path)}}),
                           capture_output=True, text=True)
        return r.returncode

    def test_digest_branch_allows_only_build(self):
        git(self.repo, "checkout", "-qb", "claude/digest-2026-10-24")
        self.assertEqual(self.hook(self.repo / "build/cards/abc.json"), 0)
        for bad in ("techdigest/render.py", ".claude/hooks/guard-run-scope.py", ".claude/settings.json",
                    "prompts/daily.md", ".github/workflows/deliver.yml", "interests.md"):
            self.assertEqual(self.hook(self.repo / bad), 2, bad)
        self.assertEqual(self.hook("/tmp/elsewhere.txt"), 2)
        self.assertEqual(self.hook(self.repo / "build/../techdigest/render.py"), 2)

    def test_interests_and_backlog_branches(self):
        git(self.repo, "checkout", "-qb", "claude/interests-2026-10-26")
        self.assertEqual(self.hook(self.repo / "interests.md"), 0)
        self.assertEqual(self.hook(self.repo / "profile.md"), 0)
        self.assertEqual(self.hook(self.repo / "sources.json"), 2)
        git(self.repo, "checkout", "-qb", "claude/backlog-triage")
        self.assertEqual(self.hook(self.repo / "backlog/triage/batch-001.json"), 0)
        self.assertEqual(self.hook(self.repo / "backlog/queue.json"), 0)
        self.assertEqual(self.hook(self.repo / "reports/bookmarks-summary.md"), 0)
        self.assertEqual(self.hook(self.repo / "backlog/raw/items.json"), 2)

    def test_other_branches_unrestricted(self):
        git(self.repo, "checkout", "-qb", "feature-x")
        self.assertEqual(self.hook(self.repo / "techdigest/render.py"), 0)

    def test_bad_input_blocks_on_run_branch(self):
        git(self.repo, "checkout", "-qb", "claude/digest-2026-10-24")
        r = subprocess.run(["python3", str(self.repo / ".claude/hooks/guard-run-scope.py")],
                           input="not json", capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_hook_is_wired_in_project_settings(self):
        settings = json.loads((ROOT / ".claude/settings.json").read_text())
        cmds = [h["command"] for m in settings["hooks"]["PreToolUse"] if "Write" in m["matcher"]
                for h in m["hooks"]]
        self.assertTrue(any("guard-run-scope.py" in c for c in cmds))

    def test_tamper_check(self):
        (self.repo / "build/reads").mkdir(parents=True)
        (self.repo / "build/candidates.json").write_text('{"candidates": []}')
        token = snapshot(self.repo)
        (self.repo / "build/cards").mkdir()
        (self.repo / "build/cards/abc.json").write_text("{}")  # the subagent's own output
        self.assertEqual(check(self.repo, token), [])
        (self.repo / "build/candidates.json").write_text('{"candidates": ["evil"]}')
        (self.repo / "techdigest/render.py").write_text("import os\n")
        (self.repo / "planted.py").write_text("x")
        self.assertEqual(check(self.repo, token), ["build/candidates.json", "tracked", "untracked"])


if __name__ == "__main__":
    unittest.main()
