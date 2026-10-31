"""Checks that the engine rules live in a path-scoped rules file and are not repeated in CLAUDE.md."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / ".claude" / "rules" / "engine.md"
CLAUDE = ROOT / "CLAUDE.md"
ENGINE_LINES = ("ROUND_HALF_UP", "never Python `round()`", "no `float()`")


def engine_problems(text):
    """List what is wrong with an engine.md text (empty list = fine)."""
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n(.*)", text, re.S)
    if not m:
        return ["no frontmatter"]
    out = []
    if "paths:" not in m.group(1) or "ectd_engine/**" not in m.group(1):
        out.append("paths frontmatter lacks ectd_engine/**")
    for word in ("Decimal", "float", "round"):
        if word not in m.group(2):
            out.append(f"body lacks {word}")
    return out


def claude_problems(text):
    """List what is wrong with a CLAUDE.md text (empty list = fine)."""
    out = []
    if len(text.splitlines()) >= 200:
        out.append("200 lines or more")
    for line in ENGINE_LINES:
        if line in text:
            out.append(f"repeats engine rule: {line}")
    if "git push" not in text:
        out.append("lost git push rule")
    if "Co-Authored-By" not in text:
        out.append("lost Co-Authored-By rule")
    if ".claude/rules/engine.md" not in text:
        out.append("no pointer to engine.md")
    return out


class RuleTests(unittest.TestCase):
    def test_engine_md_ok(self):
        self.assertTrue(ENGINE.exists())
        self.assertEqual(engine_problems(ENGINE.read_text(encoding="utf-8")), [])

    def test_claude_md_ok(self):
        self.assertEqual(claude_problems(CLAUDE.read_text(encoding="utf-8")), [])

    def test_planted_no_paths_frontmatter_detected(self):
        text = ENGINE.read_text(encoding="utf-8")
        bad = re.sub(r"\A---.*?---\r?\n", "", text, flags=re.S)
        self.assertEqual(engine_problems(bad), ["no frontmatter"])
        bad2 = text.replace("ectd_engine/**", "docs/**")
        self.assertIn("paths frontmatter lacks ectd_engine/**", engine_problems(bad2))

    def test_planted_duplicated_rules_detected(self):
        bad = CLAUDE.read_text(encoding="utf-8") + "\nNever Python `round()`, ROUND_HALF_UP, no `float()`.\n"
        self.assertTrue(any("repeats engine rule" in p for p in claude_problems(bad)))

    def test_planted_lost_project_rules_detected(self):
        text = CLAUDE.read_text(encoding="utf-8").replace("git push", "x").replace("Co-Authored-By", "y")
        self.assertEqual(sorted(claude_problems(text)), ["lost Co-Authored-By rule", "lost git push rule"])


if __name__ == "__main__":
    unittest.main()
