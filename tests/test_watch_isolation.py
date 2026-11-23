"""Guard test: the watch tests must leave a live task and its log, the real task file and every inherited git location untouched."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REAL_TASK = ROOT / ".brain" / "task.json"
REAL_LOG = ROOT / ".brain" / "activity.log"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


class WatchTestsAreIsolated(unittest.TestCase):
    def test_watch_tests_pass_and_touch_nothing_outside_their_own_temp_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / "live_project"          # stands in for the real state location (CLAUDE_PROJECT_DIR)
            (state / ".brain").mkdir(parents=True)
            task = state / ".brain" / "task.json"
            log = state / ".brain" / "activity.log"
            task.write_text('{"id": "LIVE", "allowed": ["x/**"], "start_head": null, "started": "2026-01-01T00:00:00"}', encoding="utf-8")
            log.write_text("2026-01-01T00:00:00 Edit x/live.py\n", encoding="utf-8")
            poison_index, poison_dir = Path(d) / "other_index", Path(d) / "other_git_dir"   # must stay absent
            before = (digest(task), digest(log))
            real_task_before = digest(REAL_TASK)
            real_log_before = REAL_LOG.read_bytes() if REAL_LOG.exists() else b""
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(state), GIT_INDEX_FILE=str(poison_index), GIT_DIR=str(poison_dir),
                       GIT_WORK_TREE=str(state))
            r = subprocess.run([sys.executable, "-m", "unittest", "tests.test_watch"], cwd=str(ROOT), env=env,
                               capture_output=True, text=True, timeout=900)
            self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-1500:])
            self.assertEqual((digest(task), digest(log)), before, "the live task or its log was changed by the watch tests")
            self.assertFalse(poison_index.exists() or poison_dir.exists(), "a test used an inherited git location")
            self.assertEqual(digest(REAL_TASK), real_task_before, "the real task file was changed")
            # the real log may grow (the live session's own hook appends to it) but nothing written before may change
            real_log_after = REAL_LOG.read_bytes() if REAL_LOG.exists() else b""
            self.assertTrue(real_log_after.startswith(real_log_before), "the real activity log was rewritten")


if __name__ == "__main__":
    unittest.main()
