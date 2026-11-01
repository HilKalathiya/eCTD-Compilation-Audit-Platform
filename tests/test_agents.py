"""Checks that the test-runner helper agent is read-only (cannot edit files) and cheap (haiku)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT = ROOT / ".claude" / "agents" / "test-runner.md"
RULE_LINE = "Subagents may not write code or tests. Only test-runner may be used, to run tests."


def split(text):
    """Agent .md text -> (frontmatter dict, body)."""
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n(.*)", text, re.S)
    if not m:
        raise ValueError("no frontmatter")
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, m.group(2)


def problems(text):
    """List what is wrong with one agent file text (empty list = fine)."""
    try:
        meta, body = split(text)
    except ValueError as err:
        return [str(err)]
    out = []
    if meta.get("model") != "haiku":
        out.append("model is not haiku")
    tools = sorted(t.strip() for t in meta.get("tools", "").split(",") if t.strip())
    if tools != ["Bash", "Read"]:
        out.append("tools are not exactly Bash and Read")
    if "never edit" not in body.lower():
        out.append("body does not say never edit")
    return out


class AgentTests(unittest.TestCase):
    def test_file_exists_and_is_fine(self):
        self.assertTrue(AGENT.exists())
        self.assertEqual(problems(AGENT.read_text(encoding="utf-8")), [])

    def test_name_and_description(self):
        meta, _ = split(AGENT.read_text(encoding="utf-8"))
        self.assertEqual(meta["name"], "test-runner")
        self.assertTrue(meta.get("description"))

    def test_claude_md_has_subagent_rule(self):
        self.assertIn(RULE_LINE, (ROOT / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_planted_edit_tool_refused(self):
        text = AGENT.read_text(encoding="utf-8").replace("tools: Bash, Read", "tools: Bash, Read, Edit")
        self.assertIn("tools are not exactly Bash and Read", problems(text))

    def test_planted_missing_model_refused(self):
        text = re.sub(r"^model:.*\n", "", AGENT.read_text(encoding="utf-8"), flags=re.M)
        self.assertIn("model is not haiku", problems(text))

    def test_planted_no_frontmatter_refused(self):
        self.assertEqual(problems("just text"), ["no frontmatter"])

    def test_planted_no_never_edit_refused(self):
        text = AGENT.read_text(encoding="utf-8").replace("NEVER edit", "may touch")
        self.assertIn("body does not say never edit", problems(text))


if __name__ == "__main__":
    unittest.main()
