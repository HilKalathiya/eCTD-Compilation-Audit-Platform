"""Planted-mistake tests: prove each alarm in tools/watch.py fires, and stays quiet on a clean change."""
import json
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

    def log(self, text):
        import time
        (self.root / ".brain").mkdir(exist_ok=True)
        with open(self.root / ".brain" / "activity.log", "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + text + "\n")

    def test_unlogged_writer_flagged(self):
        self.append("ectd_engine/facts/a.py", "Z = 2\n")
        self.append("tests/test_a.py", "\n    def test_two(self):\n        self.assertEqual(2, 2)\n")
        self.log("Edit tests/test_a.py")  # the log exists, but never mentions a.py
        self.assertIn("changed with no logged action: ectd_engine/facts/a.py", self.status())

    def test_logged_writer_not_flagged(self):
        self.append("ectd_engine/facts/a.py", "Z = 2\n")
        self.append("tests/test_a.py", "\n    def test_two(self):\n        self.assertEqual(2, 2)\n")
        self.log("Edit ectd_engine/facts/a.py")
        self.log("Bash echo more >> tests/test_a.py")  # a path inside a Bash command counts too
        self.assertNotIn("no logged action", self.status())

    def test_tests_timeout_is_not_ok(self):
        self.write("tests/test_slow.py", "import time, unittest\n\n\nclass S(unittest.TestCase):\n"
                   "    def test_slow(self):\n        time.sleep(8)\n")
        out = self.watch("status", "--tests", "--timeout", "1")
        self.assertIn("TIMEOUT - raise --timeout", out)
        self.assertNotIn("EXIT 0", out)

    def dirty_a(self):
        self.append("ectd_engine/facts/a.py", "Z = 2\n")
        self.append("tests/test_a.py", "\n    def test_two(self):\n        self.assertEqual(2, 2)\n")
        self.log("Edit tests/test_a.py")

    def test_cat_only_is_not_write_evidence(self):
        self.dirty_a()
        self.log("Bash cat ectd_engine/facts/a.py")
        self.assertIn("changed with no logged action: ectd_engine/facts/a.py", self.status())

    def test_long_heredoc_command_is_write_evidence(self):
        self.dirty_a()
        # ~3000 chars, many lines, and non-ASCII text (a cp1252 stdin used to drop such lines silently)
        cmd = "cat > ectd_engine/facts/a.py <<'E'\n# — ⏎\n" + "x = 1\n" * 500 + "E"
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        hook = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}},
                          ensure_ascii=False)  # real UTF-8 bytes, as Claude Code sends them
        subprocess.run([sys.executable, str(WATCH), "log"], input=hook.encode("utf-8"), env=env, timeout=60)
        logged = (self.root / ".brain" / "activity.log").read_text(encoding="utf-8").splitlines()[-1]
        self.assertGreater(len(logged), 2900)  # not cut at ~120 chars
        self.assertNotIn("no logged action", self.status())

    def run_hook(self, raw):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        subprocess.run([sys.executable, str(WATCH), "log"], input=raw, env=env, timeout=60)
        p = self.root / ".brain" / "activity.log"
        return p.read_text(encoding="utf-8").splitlines() if p.exists() else []

    def test_multiline_powershell_with_broken_character_is_logged(self):
        self.dirty_a()
        # T-031 bug: a lone surrogate (damaged em-dash, \udc97) made the UTF-8 write fail and the line vanished
        cmd = 'cd C:\\x\n$l = Get-Content STATE.md\nAdd-Content ectd_engine\\facts\\a.py -Value "## T-031 \udc97 é ⏎"\n'
        raw = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "PowerShell", "tool_input": {"command": cmd}})
        logged = self.run_hook(raw.encode("utf-8"))[-1]
        self.assertIn("PowerShell cd C:\\x", logged)
        self.assertIn("Add-Content ectd_engine\\facts\\a.py", logged)
        self.assertNotIn("LOGERROR", logged)
        self.assertNotIn("no logged action", self.status())

    def test_non_ascii_powershell_is_logged_as_utf8(self):
        raw = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "PowerShell",
                          "tool_input": {"command": "Write-Output 'café — 日本'\nGet-Date"}}, ensure_ascii=False)
        logged = self.run_hook(raw.encode("utf-8"))[-1]
        self.assertIn("café — 日本' ⏎ Get-Date", logged)

    def test_broken_input_writes_a_logerror_line(self):
        lines = self.run_hook(b"{this is not json")
        self.assertEqual(len(lines), 1)
        self.assertIn(" LOGERROR ", lines[0])
        self.assertIn("JSONDecodeError", lines[0])

    def test_copy_item_destination_is_write_evidence(self):
        self.dirty_a()
        self.log("PowerShell Copy-Item C:\\tmp\\new_a.py -Destination ectd_engine\\facts\\a.py")
        self.assertNotIn("no logged action", self.status())

    def test_copy_item_source_only_is_not_write_evidence(self):
        self.dirty_a()
        self.log("PowerShell Copy-Item ectd_engine/facts/a.py C:/tmp/backup.py")
        self.assertIn("no logged action: ectd_engine/facts/a.py", self.status())

    def test_run_timeout_exit_code_is_124(self):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        r = subprocess.run([sys.executable, str(WATCH), "run", f'"{sys.executable}" -c "import time; time.sleep(8)"',
                            "--timeout", "1"], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 124)
        self.assertIn("TIMEOUT - raise --timeout", r.stdout)

    def test_clean_change_raises_no_flag(self):
        self.append("ectd_engine/facts/a.py", "Z = 2\n")
        self.append("tests/test_a.py", "\n    def test_two(self):\n        self.assertEqual(2, 2)\n")
        self.assertIn("FLAGS: none", self.status())


if __name__ == "__main__":
    unittest.main()
