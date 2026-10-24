import json
import unittest

from techdigest.config import ConfigError, load_config, parse_config

from helpers import ROOT, TempDir


def cfg(*sources):
    return {"sources": list(sources)}


GOOD = {"id": "a", "name": "A", "type": "feed", "url": "https://example.com/a"}


class ConfigTest(unittest.TestCase):
    def test_repository_sources_json_is_valid(self):
        c = load_config(ROOT / "sources.json")
        self.assertGreater(len(c.enabled_sources()), 15)
        self.assertEqual(c.timezone, "America/Chicago")

    def test_every_enabled_source_has_a_fixture(self):
        c = load_config(ROOT / "sources.json")
        missing = [s.id for s in c.enabled_sources()
                   if not list((ROOT / "fixtures/feeds").glob(f"{s.id}.*"))]
        self.assertEqual(missing, [], "add a fixture in fixtures/build.py for each new source")

    def test_disabled_placeholder_may_have_empty_url(self):
        c = parse_config(cfg(GOOD, {**GOOD, "id": "b", "url": "", "enabled": False}))
        self.assertEqual([s.id for s in c.enabled_sources()], ["a"])

    def test_errors_name_the_offending_source(self):
        cases = [
            ({**GOOD, "type": "podcast"}, "source `a`"),
            ({**GOOD, "url": "ftp://x"}, "source `a`"),
            ({**GOOD, "colour": "red"}, "unknown field"),
            ({**GOOD, "type": "html_links"}, "needs a `pattern`"),
            ({**GOOD, "id": "Bad Id"}, "`id` must be"),
        ]
        for bad, msg in cases:
            with self.subTest(bad=bad):
                with self.assertRaises(ConfigError) as e:
                    parse_config(cfg(bad))
                self.assertIn(msg, str(e.exception))

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ConfigError):
            parse_config(cfg(GOOD, GOOD))

    def test_invalid_json_reports_line(self):
        with TempDir() as d:
            p = d / "sources.json"
            p.write_text('{\n "sources": [,]\n}')
            with self.assertRaises(ConfigError) as e:
                load_config(p)
            self.assertIn("line 2", str(e.exception))

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config("/nonexistent/sources.json")


if __name__ == "__main__":
    unittest.main()
