"""Tests that crosscheck.py never exits non-zero silently: 0 = match, 1 = mismatch, 2 = could not run (reason on stderr and in crosscheck_error.txt)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import build

ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-m", "ectd_engine.summary.crosscheck", *args], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, timeout=120)


class ExitCodes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name) / "run"
        facts = G.collect()
        build.write_run(cls.base, facts)
        cls.snap = Path(cls.tmp.name) / "snapshot.json"
        cls.snap.write_text(json.dumps(facts, sort_keys=True), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def out_dir(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return Path(d.name) / "out"

    def test_clean_run_exits_0(self):
        out = self.out_dir()
        r = run_cli(str(self.base), "--snapshot", str(self.snap), "--out", str(out))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(list(out.glob("crosscheck_error*.txt")))

    def test_a_mismatch_exits_1_not_2(self):
        folder = Path(tempfile.mkdtemp()) / "bad"
        import shutil
        shutil.copytree(self.base, folder)
        html = (folder / "M23.html").read_text(encoding="utf-8")
        self.assertEqual(html.count(">36</span> months when stored"), 1)
        (folder / "M23.html").write_text(html.replace(">36</span> months when stored", ">24</span> months when stored"), encoding="utf-8")
        out = self.out_dir()
        r = run_cli(str(folder), "--snapshot", str(self.snap), "--out", str(out))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertFalse(list(out.glob("crosscheck_error*.txt")))
        shutil.rmtree(folder.parent, ignore_errors=True)

    def test_dead_neo4j_port_exits_2_with_a_written_reason(self):
        out = self.out_dir()
        r = run_cli(str(self.base), "--out", str(out), env_extra={"NEO4J_URI": "bolt://127.0.0.1:1", "NEO4J_PASSWORD": "x"})
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("crosscheck could not run", r.stderr)
        text = (out / "crosscheck_error.txt").read_text(encoding="utf-8")
        self.assertIn("exit 2", text)
        self.assertGreater(len(text.strip().splitlines()[-1]), 5)   # a real reason line, not an empty file

    def test_missing_snapshot_file_exits_2_with_a_written_reason(self):
        out = self.out_dir()
        r = run_cli(str(self.base), "--snapshot", str(out.parent / "no_such_snapshot.json"), "--out", str(out))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("FileNotFoundError", r.stderr)
        self.assertIn("FileNotFoundError", (out / "crosscheck_error.txt").read_text(encoding="utf-8"))

    def test_missing_run_folder_exits_2_with_a_written_reason(self):
        out = self.out_dir()
        r = run_cli(str(out.parent / "no_such_run"), "--snapshot", str(self.snap), "--out", str(out))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("could not run", r.stderr)
        self.assertTrue((out / "crosscheck_error.txt").exists())

    def test_an_existing_error_file_is_never_overwritten(self):
        out = self.out_dir()
        for _ in range(2):
            r = run_cli(str(out.parent / "no_such_run"), "--snapshot", str(self.snap), "--out", str(out))
            self.assertEqual(r.returncode, 2)
        self.assertEqual(sorted(p.name for p in out.glob("crosscheck_error*.txt")), ["crosscheck_error.txt", "crosscheck_error_2.txt"])


if __name__ == "__main__":
    unittest.main()
