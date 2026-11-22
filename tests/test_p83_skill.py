"""Tests the p83-stability Agent Skill: well formed, same entry point as the direct run, and the compare tool catches a planted verdict change."""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ectd_engine.stability import compare as C, facts as F

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "p83-stability"


def run_script(path, out):
    return subprocess.run([sys.executable, str(path), "--backend", "mock", "--out", str(out)], capture_output=True, text=True, cwd=str(ROOT))


class SkillFile(unittest.TestCase):
    def test_skill_md_has_name_and_description(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        head = text.split("---")[1]
        self.assertIn("name: p83-stability", head)
        self.assertIn("description:", head)
        for word in ("When to use", "Inputs", "Steps"):
            self.assertIn(word, text)


def skill_counts(text):
    """(public rows, DEMO rows) as the SKILL.md text states them, or None if the sentence is missing."""
    m = re.search(r"(\d+) public rows, (\d+) DEMO rows", text)
    return (int(m.group(1)), int(m.group(2))) if m else None


class SkillMatchesData(unittest.TestCase):
    def test_skill_md_row_counts_match_the_csv(self):
        rows = F.load_rows()
        self.assertEqual(skill_counts((SKILL / "SKILL.md").read_text(encoding="utf-8")), F.count_sources(rows))
        self.assertEqual(F.count_sources(rows)[0], 6)

    def test_planted_wrong_count_is_caught(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8").replace("6 public rows", "4 public rows")
        self.assertNotEqual(skill_counts(text), F.count_sources(F.load_rows()))


class KindNames(unittest.TestCase):
    def test_old_name_is_gone_and_new_name_is_the_default(self):
        spec = importlib.util.spec_from_file_location("writer_run_kinds", ROOT / "tools" / "writer_run.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with self.assertRaises(SystemExit):
            mod.main(["--kind", "p83old", "--backend", "mock", "--out", tempfile.gettempdir()])
        text = (ROOT / "tools" / "writer_run.py").read_text(encoding="utf-8")
        self.assertIn('choices=["p83", "p83_8task", "p54", "p56"], default="p83_8task"', text)
        self.assertNotIn("p83old", text)


class SameEntryPoint(unittest.TestCase):
    def test_skill_script_uses_the_same_writer_run_file(self):
        spec = importlib.util.spec_from_file_location("p83_skill_run", SKILL / "scripts" / "run.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(Path(mod.writer_run.__file__).resolve(), (ROOT / "tools" / "writer_run.py").resolve())

    def test_mock_skill_run_equals_mock_direct_run(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a = subprocess.run([sys.executable, str(ROOT / "tools" / "writer_run.py"), "--kind", "p83", "--backend", "mock",
                                "--out", str(d / "direct")], capture_output=True, text=True, cwd=str(ROOT))
            b = run_script(SKILL / "scripts" / "run.py", d / "skill")
            self.assertEqual((a.returncode, b.returncode), (0, 0), a.stderr + b.stderr)
            ra, _ = C.load(d / "direct")
            rb, _ = C.load(d / "skill")
            rows = C.compare(ra, rb)
            self.assertEqual(len(rows), 10)
            self.assertTrue(all(r["same"] for r in rows))
            self.assertEqual(C.main([str(d / "direct"), str(d / "skill"), "--out", str(d / "compare.md")]), 0)
            self.assertIn("10 of 10 tasks have the same verdict", (d / "compare.md").read_text(encoding="utf-8"))


class CompareCanFail(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = Path(self.tmp)
        r = run_script(SKILL / "scripts" / "run.py", self.d / "direct")
        self.assertEqual(r.returncode, 0, r.stderr)
        shutil.copytree(self.d / "direct", self.d / "skill")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def edit_skill(self, fn):
        lines = [json.loads(x) for x in (self.d / "skill" / "results.jsonl").read_text(encoding="utf-8").splitlines()]
        fn(lines)
        (self.d / "skill" / "results.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")

    def test_identical_folders_pass(self):
        self.assertEqual(C.main([str(self.d / "direct"), str(self.d / "skill")]), 0)

    def test_planted_accepted_to_rejected_is_caught(self):
        def flip(lines):
            lines[0]["accepted"] = False
            lines[0]["drafts"][-1]["passed"] = False
        self.edit_skill(flip)
        out = self.d / "compare.md"
        self.assertEqual(C.main([str(self.d / "direct"), str(self.d / "skill"), "--out", str(out)]), 1)
        text = out.read_text(encoding="utf-8")
        self.assertIn("**NO**", text)
        self.assertIn("9 of 10 tasks have the same verdict", text)

    def test_planted_changed_problem_is_caught_and_diff_shown(self):
        def change(lines):
            lines[1]["drafts"][0]["problems"] = ["missing placeholder [[min]]"]
            lines[1]["drafts"][0]["text"] = "Another draft."
        self.edit_skill(change)
        a, _ = C.load(self.d / "direct")
        b, _ = C.load(self.d / "skill")
        rows = C.compare(a, b)
        bad = [r for r in rows if not r["same"]]
        self.assertEqual(len(bad), 1)
        self.assertTrue(bad[0]["diff"])

    def test_planted_missing_task_is_caught(self):
        self.edit_skill(lambda lines: lines.pop())
        self.assertEqual(C.main([str(self.d / "direct"), str(self.d / "skill")]), 1)

    def test_timing_difference_is_ignored(self):
        def slower(lines):
            for x in lines:
                for dr in x["drafts"]:
                    dr["seconds"] = 99
        self.edit_skill(slower)
        self.assertEqual(C.main([str(self.d / "direct"), str(self.d / "skill")]), 0)


if __name__ == "__main__":
    unittest.main()
