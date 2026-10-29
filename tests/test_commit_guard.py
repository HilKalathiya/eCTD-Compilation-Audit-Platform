"""Planted-mistake tests: prove tools/commit_guard.py blocks unsaved or unpushed work, and stays quiet when all is pushed."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "tools" / "commit_guard.py"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]


class CommitGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.remote = base / "remote.git"
        self.root = base / "work"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "a.txt").write_text("a\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-q", "-u", "origin", "HEAD")

    def git(self, *args):
        subprocess.run(GIT + list(args), cwd=self.root, check=True, capture_output=True)

    def guard(self, payload=None, **extra_env):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root), **extra_env)
        r = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload or {}),
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def test_clean_and_pushed_is_quiet(self):
        self.assertIsNone(self.guard())

    def test_uncommitted_change_blocks(self):
        (self.root / "a.txt").write_text("changed\n")
        out = self.guard()
        self.assertEqual(out["decision"], "block")
        self.assertIn("not committed", out["reason"])

    def test_unpushed_commit_blocks(self):
        (self.root / "b.txt").write_text("b\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "local only")
        out = self.guard()
        self.assertEqual(out["decision"], "block")
        self.assertIn("not pushed", out["reason"])

    def test_second_stop_is_let_through(self):
        (self.root / "a.txt").write_text("changed\n")
        self.assertIsNone(self.guard({"stop_hook_active": True}))

    def test_git_missing_does_not_crash(self):
        (self.root / "a.txt").write_text("changed\n")
        empty = Path(self._tmp.name) / "empty"
        empty.mkdir()
        # no git on PATH and nowhere else: the hook must exit 0 quietly, not print a traceback
        hide = {k: str(empty) for k in ("PATH", "ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA")}
        self.assertIsNone(self.guard(CLAUDE_CODE_GIT_BASH_PATH="", **hide))


if __name__ == "__main__":
    unittest.main()
