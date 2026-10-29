"""Tests that the Plain words output style file is valid and that settings.json names it with the exact same case."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / ".claude" / "output-styles" / "plain-words.md"
SETTINGS = ROOT / ".claude" / "settings.json"


def parse(text):
    """Split a style file into (frontmatter dict, body lines)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("no frontmatter")
    end = lines.index("---", 1)
    meta = {}
    for ln in lines[1:end]:
        k, _, v = ln.partition(":")
        meta[k.strip()] = v.strip()
    return meta, [l for l in lines[end + 1:] if l.strip()]


def style_matches(settings_value, name):
    return settings_value == name


class OutputStyleTests(unittest.TestCase):
    def setUp(self):
        self.meta, self.body = parse(STYLE.read_text(encoding="utf-8"))

    def test_file_exists_and_frontmatter_parses(self):
        self.assertTrue(STYLE.is_file())
        self.assertEqual(self.meta["name"], "Plain words")
        self.assertTrue(self.meta["description"])

    def test_keeps_coding_instructions(self):
        self.assertEqual(self.meta["keep-coding-instructions"], "true")

    def test_body_is_short(self):
        self.assertLess(len(self.body), 15)

    def test_settings_name_matches_exactly(self):
        s = json.loads(SETTINGS.read_text(encoding="utf-8"))
        self.assertTrue(style_matches(s["outputStyle"], self.meta["name"]))

    def test_hooks_and_deny_list_still_there(self):
        s = json.loads(SETTINGS.read_text(encoding="utf-8"))
        self.assertIn("hooks", s)
        self.assertTrue(s["permissions"]["deny"])
        self.assertIn("attribution", s)

    def test_planted_wrong_case_is_detected(self):
        self.assertFalse(style_matches("plain words", self.meta["name"]))

    def test_planted_missing_frontmatter_fails(self):
        with self.assertRaises(ValueError):
            parse("just text\n")


if __name__ == "__main__":
    unittest.main()
