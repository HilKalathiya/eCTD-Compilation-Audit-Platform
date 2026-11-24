"""Tests for T-073 item 5: a tool call that ENDS IN ERROR is written to the activity log, marked FAILED with its exit code, and never counts as proof that a file was written."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
WATCH = ROOT / "tools" / "watch.py"


def clean_env(**extra):
    """The environment without any inherited git location, so a test can never reach the real repository."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra)
    return env


class FailedCalls(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def log_event(self, payload):
        r = subprocess.run([sys.executable, str(WATCH), "log"], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                           env=clean_env(CLAUDE_PROJECT_DIR=str(self.root)), capture_output=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        p = self.root / ".brain" / "activity.log"
        return p.read_text(encoding="utf-8").splitlines() if p.exists() else []

    def test_a_failing_bash_call_is_logged_with_its_exit_code(self):
        lines = self.log_event({"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_input": {"command": "python -c 'raise SystemExit(3)'"},
                                "error": "Exit code 3\nboom", "is_interrupt": False})
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], r"^\S+ FAILED Bash python -c 'raise SystemExit\(3\)' \[exit 3\] keys=")

    def test_an_error_without_an_exit_code_says_so(self):
        lines = self.log_event({"hook_event_name": "PostToolUseFailure", "tool_name": "Edit", "tool_input": {"file_path": str(self.root / "x.py")},
                                "error": "String to replace not found"})
        self.assertIn("FAILED Edit x.py [exit ?]", lines[0])

    def test_an_interrupted_call_is_marked(self):
        lines = self.log_event({"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_input": {"command": "sleep 99"},
                                "error": "Exit code 130", "is_interrupt": True})
        self.assertIn("[exit 130; interrupted]", lines[0])

    def test_a_successful_call_is_logged_as_before(self):
        lines = self.log_event({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "echo hi"}, "tool_response": {}})
        self.assertTrue(lines[0].endswith(" Bash echo hi"), lines)
        self.assertNotIn("FAILED", lines[0])

    def test_a_failed_edit_or_command_is_not_proof_that_a_file_was_written(self):
        with mock.patch.dict(os.environ, clean_env(CLAUDE_PROJECT_DIR=str(self.root)), clear=True):
            spec = importlib.util.spec_from_file_location("watch_failed_evidence", WATCH)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        for event in ({"tool_name": "Edit", "tool_input": {"file_path": str(self.root / "a.py")}},
                      {"tool_name": "Write", "tool_input": {"file_path": str(self.root / "a.py")}},
                      {"tool_name": "Bash", "tool_input": {"command": "echo x > a.py"}}):
            lines = self.log_event(dict(event, hook_event_name="PostToolUseFailure", error="Exit code 1"))
            acts = [(l[20:].partition(" ")[0], l[20:].partition(" ")[2]) for l in lines]
            self.assertFalse(mod.has_write_evidence("a.py", acts), event)
        ok = self.log_event({"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(self.root / "a.py")}})
        self.assertTrue(mod.has_write_evidence("a.py", [(l[20:].partition(" ")[0], l[20:].partition(" ")[2]) for l in ok]))

    def test_the_hook_is_configured(self):
        hooks = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["hooks"]
        entries = hooks["PostToolUseFailure"]
        self.assertTrue(any("Bash" in e["matcher"] and e["hooks"][0]["args"][1:] == ["log"] and e["hooks"][0]["args"][0].endswith("tools/watch.py")
                            for e in entries))
        self.assertIn("PostToolUse", hooks)                      # the success hook is still there


if __name__ == "__main__":
    unittest.main()
