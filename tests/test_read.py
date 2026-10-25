import json
import unittest

from techdigest.read import HEADER, extract_article, plan_fetch, read_many, read_url

from helpers import ROOT, TempDir

READS = ROOT / "fixtures/reads"
URLMAP = json.loads((READS / "urls.json").read_text())


def getter(url):
    if url not in URLMAP:
        raise RuntimeError("HTTP 404")
    return (READS / URLMAP[url]).read_bytes()


class ExtractTest(unittest.TestCase):
    def test_article_beats_nav_sidebar_comments_footer(self):
        title, text = extract_article((READS / "blog.html").read_text())
        self.assertEqual(title, "Splitting a reviewer into a fresh-context subagent (fixture)")
        self.assertIn("flagged 31 issues", text)
        self.assertIn("## What we changed", text)
        self.assertIn("reviewer: tools: Read, Grep, Bash", text)
        for noise in ("Subscribe", "SEO agency", "Copyright", "Home"):
            self.assertNotIn(noise, text)

    def test_densest_block_without_article_or_main(self):
        _, text = extract_article((READS / "no-article.html").read_text())
        self.assertIn("WebGPU execution", text)
        self.assertNotIn("Contact sales", text)
        self.assertNotIn("Status page", text)


class RouteTest(unittest.TestCase):
    def test_routes(self):
        self.assertEqual(plan_fetch("https://github.com/example/skill-lint"),
                         ("markdown", "https://raw.githubusercontent.com/example/skill-lint/HEAD/README.md"))
        self.assertEqual(plan_fetch("https://github.com/o/r/blob/main/docs/guide.md")[1],
                         "https://raw.githubusercontent.com/o/r/main/docs/guide.md")
        self.assertEqual(plan_fetch("https://arxiv.org/abs/2610.12345v2"), ("html", "https://arxiv.org/abs/2610.12345"))
        for url in ("https://x.com/a/status/1", "https://www.youtube.com/watch?v=abcdefghijk",
                    "https://www.reddit.com/r/x/comments/1/", "https://news.ycombinator.com/item?id=1",
                    "https://e.com/paper.pdf", "https://github.com/o/r/issues/5"):
            self.assertEqual(plan_fetch(url)[0], "skip", url)


class ReadTest(unittest.TestCase):
    def test_statuses(self):
        self.assertEqual(read_url("a", "https://example.org/blog/fresh-reviewer", getter).status, "ok")
        thin = read_url("b", "https://example.org/app", getter)
        self.assertEqual(thin.status, "thin")
        self.assertEqual(read_url("c", "https://example.org/gone", getter).status, "failed")
        skipped = read_url("d", "https://x.com/a/status/1", getter)
        self.assertEqual((skipped.status, skipped.reason[:5]), ("skipped", "x.com"))

    def test_github_readme_fallback_to_lowercase(self):
        calls = []

        def g(url):
            calls.append(url)
            if url.endswith("/README.md"):
                raise RuntimeError("HTTP 404")
            return b"# lower\n\n" + b"word " * 200
        r = read_url("e", "https://github.com/o/r", g)
        self.assertEqual(r.status, "ok")
        self.assertTrue(calls[-1].endswith("/readme.md"))

    def test_files_are_marked_untrusted_and_index_has_no_text(self):
        items = [("a", "https://example.org/blog/fresh-reviewer"), ("b", "https://example.org/gone"),
                 ("c", "https://github.com/example/skill-lint")]
        with TempDir() as d:
            index = read_many(items, d, getter, sleep=lambda s: None, log=lambda *a: None)
            text = (d / "a.md").read_text()
            self.assertTrue(text.startswith(HEADER))
            self.assertTrue(text.rstrip().endswith(HEADER))
            self.assertEqual(index["b"]["status"], "failed")
            self.assertEqual(index["c"]["status"], "ok")
            self.assertNotIn("flagged 31", (d / "index.json").read_text())

    def test_ok_results_are_cached(self):
        calls = []

        def g(url):
            calls.append(url)
            return getter(url)
        with TempDir() as d:
            for _ in range(2):
                read_many([("a", "https://example.org/blog/fresh-reviewer")], d, g,
                          sleep=lambda s: None, log=lambda *a: None)
        self.assertEqual(len(calls), 1)

    def test_long_pages_are_cut(self):
        r = read_url("f", "https://e.com/long", lambda u: ("<article>" + "<p>" + "word " * 300 + "</p>" * 1 + "</article>") .encode() * 1)
        self.assertEqual(r.status, "ok")
        big = read_url("g", "https://e.com/big", lambda u: ("<article>" + ("<p>" + "word " * 100 + "</p>") * 100 + "</article>").encode())
        self.assertLessEqual(len(big.text), 30_100)
        self.assertIn("cut at 30,000 characters", big.text)


if __name__ == "__main__":
    unittest.main()
