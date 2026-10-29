"""Planted-mistake tests: prove the PreToolUse guard in tools/watch.py blocks frozen-file edits and nothing else."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WATCH = Path(__file__).resolve().parent.parent / "tools" / "watch.py"


class GuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".brain").mkdir()
        self.set_task(["ectd_engine/**", "tests/**"])

    def set_task(self, allowed):
        (self.root / ".brain" / "task.json").write_text(json.dumps({"id": "X", "allowed": allowed}), encoding="utf-8")

    def guard(self, stdin):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        r = subprocess.run([sys.executable, str(WATCH), "guard"], input=stdin, env=env,
                           capture_output=True, text=True, timeout=30)
        return r.returncode, r.stderr

    def call(self, tool, path, key="file_path"):
        return self.guard(json.dumps({"tool_name": tool, "tool_input": {key: path}}))

    def test_write_frozen_blocked(self):
        code, err = self.call("Write", "writer_test/x.py")
        self.assertEqual(code, 2)
        self.assertIn("FROZEN", err)

    def test_absolute_frozen_path_blocked(self):
        self.assertEqual(self.call("Edit", str(self.root / "writer_test" / "README.md"))[0], 2)

    def test_settings_blocked_without_task_allowing(self):
        self.assertEqual(self.call("Edit", ".claude/settings.json")[0], 2)

    def test_no_task_blocks_frozen(self):
        (self.root / ".brain" / "task.json").unlink()
        self.assertEqual(self.call("MultiEdit", "handoff/x.md")[0], 2)

    def test_notebook_frozen_blocked(self):
        self.assertEqual(self.call("NotebookEdit", "writer_test/n.ipynb", key="notebook_path")[0], 2)

    def test_frozen_allowed_by_task(self):
        self.set_task([".claude/**"])
        self.assertEqual(self.call("Edit", ".claude/settings.json")[0], 0)

    def test_allowed_path_ok(self):
        self.assertEqual(self.call("Edit", "ectd_engine/facts/schema.py")[0], 0)

    def test_read_frozen_ok(self):
        self.assertEqual(self.call("Read", "writer_test/README.md")[0], 0)

    def test_garbage_stdin_ok(self):
        self.assertEqual(self.guard("not json {")[0], 0)
        self.assertEqual(self.guard("")[0], 0)


if __name__ == "__main__":
    unittest.main()
