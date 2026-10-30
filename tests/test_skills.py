"""Checks that the four slash-command skills are well formed and lost nothing from the old commands."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
NAMES = ("where", "explain", "recap", "verify")


def split(text):
    """SKILL.md text -> (frontmatter dict, body)."""
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n(.*)", text, re.S)
    if not m:
        raise ValueError("no frontmatter")
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, m.group(2)


def problems(text):
    """List what is wrong with one SKILL.md text (empty list = fine)."""
    try:
        meta, _ = split(text)
    except ValueError as err:
        return [str(err)]
    out = []
    if not meta.get("description"):
        out.append("missing description")
    if meta.get("disable-model-invocation") != "true":
        out.append("disable-model-invocation is not true")
    if not meta.get("name"):
        out.append("missing name")
    return out


def old_command(name):
    """Old command body from git history (the folder is removed after this task)."""
    p = ROOT / ".claude" / "commands" / f"{name}.md"
    if p.exists():
        return split(p.read_text(encoding="utf-8"))[1]
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    path = f".claude/commands/{name}.md"
    ref = git("show", f"HEAD:{path}")
    if ref.returncode != 0:  # deleted: read the last commit that still had it
        last = git("rev-list", "-1", "HEAD", "--", path).stdout.strip()
        ref = git("show", f"{last}^:{path}") if last else ref
    return split(ref.stdout)[1] if ref.returncode == 0 else None


class SkillTests(unittest.TestCase):
    def test_four_files_exist_and_parse(self):
        for n in NAMES:
            p = SKILLS / n / "SKILL.md"
            self.assertTrue(p.exists(), n)
            self.assertEqual(problems(p.read_text(encoding="utf-8")), [], n)

    def test_names_unique_and_match_folder(self):
        names = [split((SKILLS / n / "SKILL.md").read_text(encoding="utf-8"))[0]["name"] for n in NAMES]
        self.assertEqual(names, list(NAMES))
        self.assertEqual(len(set(names)), 4)

    def test_verify_only_runs_watch_py(self):
        meta, body = split((SKILLS / "verify" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["allowed-tools"], "Bash(python tools/watch.py *)")
        self.assertIn("python tools/watch.py status --tests", body)

    def test_old_command_text_kept(self):
        for n in ("where", "explain", "recap"):
            old = old_command(n)
            self.assertIsNotNone(old, f"old {n} command not found in git history")
            body = split((SKILLS / n / "SKILL.md").read_text(encoding="utf-8"))[1]
            self.assertEqual(body.strip().replace("\r\n", "\n"), old.strip().replace("\r\n", "\n"), n)

    def test_explain_keeps_arguments(self):
        body = split((SKILLS / "explain" / "SKILL.md").read_text(encoding="utf-8"))[1]
        self.assertIn("$ARGUMENTS", body)

    def test_planted_missing_description_detected(self):
        bad = "---\nname: x\ndisable-model-invocation: true\n---\nbody\n"
        self.assertIn("missing description", problems(bad))

    def test_planted_model_invocation_on_detected(self):
        bad = "---\nname: x\ndescription: d\n---\nbody\n"
        self.assertIn("disable-model-invocation is not true", problems(bad))

    def test_planted_no_frontmatter_detected(self):
        self.assertEqual(problems("just text"), ["no frontmatter"])


if __name__ == "__main__":
    unittest.main()
