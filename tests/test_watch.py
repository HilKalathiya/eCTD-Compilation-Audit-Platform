"""Planted-mistake tests: prove each alarm in tools/watch.py fires, and stays quiet on a clean change."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WATCH = Path(__file__).resolve().parent.parent / "tools" / "watch.py"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]

# Planted-mistake text is assembled from pieces so this file itself does not trip the alarms it tests.
SKIP = "@unittest." + "skip('x')"
KEY = "api_" + "key"

TEST_A = "import unittest\n\n\nclass A(unittest.TestCase):\n    def test_one(self):\n        self.assertTrue(True)\n"


class WatchFlagTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.write("writer_test/README.md", "frozen readme\n")
        self.write("ectd_engine/facts/a.py", '"""a."""\nX = 1\n')
        self.write("tests/test_a.py", TEST_A)
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.watch("task", "X", "ectd_engine/**", "tests/**")

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    def append(self, rel, text):
        with open(self.root / rel, "a", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def git(self, *args):
        subprocess.run([*GIT, "-C", str(self.root), *args], check=True, capture_output=True)

    def watch(self, *args):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        r = subprocess.run([sys.executable, str(WATCH), *args], env=env, capture_output=True,
                           text=True, timeout=60)
        return r.stdout

    def status(self):
        return self.watch("status")

    def test_frozen_path_touched(self):
        self.append("writer_test/README.md", "planted\n")
        self.assertIn("FROZEN path touched", self.status())

    def test_tests_removed(self):
        self.write("tests/test_a.py", "import unittest\n")
        self.assertIn("TESTS REMOVED", self.status())

    def test_skip_added(self):
        self.write("tests/test_a.py", TEST_A.replace("    def test_one", "    " + SKIP + "\n    def test_one"))
        self.assertIn("skip/x" + "fail ADDED", self.status())

    def test_round_used(self):
        self.write("ectd_engine/facts/b.py", '"""b."""\nY = round(1.5)\n')
        self.assertIn("round() used", self.status())

    def test_float_used(self):
        self.write("ectd_engine/facts/b.py", '"""b."""\nY = float("1.5")\n')
        self.assertIn("float() used", self.status())

    def test_engine_changed_without_test(self):
        self.append("ectd_engine/facts/a.py", "Z = 2\n")
        self.assertIn("NO test file changed", self.status())

    def test_outside_task_scope(self):
        self.write("docs/x.md", "stray\n")
        self.assertIn("outside task scope", self.status())

    def test_possible_secret(self):
        self.write("ectd_engine/facts/c.py", '"""c."""\n' + KEY + ' = "abcd1234efgh"\n')
        self.assertIn("possible secret", self.status())

    def test_assertions_weakened(self):
        four = "    def test_one(self):\n" + "".join(f"        self.assertEqual({i}, {i})\n" for i in range(3))
        self.write("tests/test_a.py", "import unittest\n\n\nclass A(unittest.TestCase):\n" + four)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "three asserts")
        self.watch("task", "X", "ectd_engine/**", "tests/**")
        self.write("tests/test_a.py", "import unittest\n\n\nclass A(unittest.TestCase):\n"
                   "    def test_one(self):\n        pass\n")
        self.assertIn("assertions net -3", self.status())

    def test_requirements_changed(self):
        self.write("requirements.txt", "somelib==1.0\n")
        self.assertIn("requirements.txt changed", self.status())

    def test_large_file(self):
        (self.root / "ectd_engine").mkdir(exist_ok=True)
        (self.root / "ectd_engine" / "big.bin").write_bytes(b"x" * 1_100_000)
        self.assertIn("large file (>1 MB)", self.status())

    def test_clean_change_raises_no_flag(self):
        self.append("ectd_engine/facts/a.py", "Z = 2\n")
        self.append("tests/test_a.py", "\n    def test_two(self):\n        self.assertEqual(2, 2)\n")
        self.assertIn("FLAGS: none", self.status())


if __name__ == "__main__":
    unittest.main()
