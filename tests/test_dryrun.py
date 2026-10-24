import hashlib
import re
import unittest
import urllib.request
from unittest import mock

from techdigest.dryrun import dry_run

from helpers import ROOT, TempDir


def tree_hash(path):
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(path)).encode() + p.read_bytes())
    return h.hexdigest()


class DryRunTest(unittest.TestCase):
    def test_offline_from_fixtures_without_touching_state(self):
        before = tree_hash(ROOT / "state")
        with TempDir() as d, mock.patch.object(urllib.request, "urlopen",
                                               side_effect=AssertionError("network used")):
            md_path = dry_run(ROOT / "sources.json", ROOT / "fixtures", d / "out", log=lambda *a: None)
            md = md_path.read_text()
            self.assertEqual(md_path.name, "2026-10-23.md")
            self.assertEqual(re.findall(r"^## (.+)$", md, re.M),
                             ["🏆 Top 3", "👀 Worth a skim", "🔧 Changed in my tools"])
            self.assertEqual(len(re.findall(r"^### \d\. ", md, re.M)), 3)
            # dedupe: the already-seen fixture items do not appear
            self.assertNotIn("fixture-old-post", md)
            self.assertNotIn("item?id=1000003", md)
            # merge: the Simon Willison post carries its HN thread
            self.assertRegex(md, r"fixture-context/\) · \[HN · 412 points, 230 comments\]")
            # page watch reports the changed policy text
            self.assertIn("Chrome Web Store program policies changed", md)
            # failing fixture sources are listed, grouped by error
            self.assertIn("failed today: Reddit (HTTP 429); AI Engineer (YouTube), "
                          "Latent Space (YouTube), AI Explained (YouTube) (HTTP 404)", md)
            self.assertTrue((d / "out/state/seen.json").exists())
        self.assertEqual(tree_hash(ROOT / "state"), before, "dry run must not modify state/")

    def test_sample_digest_is_current(self):
        with TempDir() as d:
            md = dry_run(ROOT / "sources.json", ROOT / "fixtures", d / "out", log=lambda *a: None)
            self.assertEqual(md.read_text(), (ROOT / "examples/sample-digest.md").read_text(),
                             "regenerate: python3 -m techdigest dry-run && "
                             "cp build/dry-run/digest/2026-10-23.md examples/sample-digest.md")


if __name__ == "__main__":
    unittest.main()
