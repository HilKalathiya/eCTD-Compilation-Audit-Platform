"""Planted-mistake tests: prove each alarm in tools/watch.py fires, and stays quiet on a clean change."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

WATCH = Path(__file__).resolve().parent.parent / "tools" / "watch.py"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]

# Planted-mistake text is assembled from pieces so this file itself does not trip the alarms it tests.
SKIP = "@unittest." + "skip('x')"
KEY = "api_" + "key"

TEST_A = "import unittest\n\n\nclass A(unittest.TestCase):\n    def test_one(self):\n        self.assertTrue(True)\n"


def git_retry(root, *args, run=subprocess.run, tries=3, pause=0.3):
    """Run one git command in root; if it fails, wait a moment and try again (up to `tries` times), then raise with git's message."""
    last = None
    for attempt in range(tries):
        try:  # Windows sometimes refuses to start the program at all (WinError 5): that counts as a failed try too
            last = run([*GIT, "-C", str(root), *args], capture_output=True, text=True)
        except OSError as e:
            last = subprocess.CompletedProcess(args, -1, "", f"{type(e).__name__}: {e}")
        if last.returncode == 0:
            return last
        if attempt < tries - 1:
            time.sleep(pause)
    raise RuntimeError(f"git {' '.join(args)} failed {tries}x, exit {last.returncode}: {last.stderr.strip()}")


def run_retry(cmd, tries=3, pause=0.3, **kw):
    """subprocess.run that tries again when Windows refuses to start the program (WinError 5)."""
    for attempt in range(tries):
        try:
            return subprocess.run(cmd, **kw)
        except PermissionError:
            if attempt == tries - 1:
                raise
            time.sleep(pause)


def build_repo(root, run=subprocess.run, pause=0.3):
    """Turn root into a git repo with one 'base' commit (author set locally) and check that the commit really exists."""
    git_retry(root, "init", "-q", run=run, pause=pause)
    git_retry(root, "config", "user.name", "t", run=run, pause=pause)
    git_retry(root, "config", "user.email", "t@t", run=run, pause=pause)
    git_retry(root, "add", "-A", run=run, pause=pause)
    git_retry(root, "commit", "-q", "-m", "base", run=run, pause=pause)
    git_retry(root, "rev-parse", "--verify", "HEAD", run=run, pause=pause)


class WatchFlagTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.write("writer_test/README.md", "frozen readme\n")
        self.write("ectd_engine/facts/a.py", '"""a."""\nX = 1\n')
        self.write("tests/test_a.py", TEST_A)
        build_repo(self.root)
        self.watch("task", "X", "ectd_engine/**", "tests/**")

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    def append(self, rel, text):
        with open(self.root / rel, "a", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def git(self, *args):
        git_retry(self.root, *args)

    def watch(self, *args):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        r = run_retry([sys.executable, str(WATCH), *args], env=env, capture_output=True,
                      text=True, timeout=60)
        return r.stdout

    def status(self):
        # tools/watch.py hides a failed git call and then prints "CHANGED ... 0 file(s)". If git itself shows changes
        # but the watcher says 0, that was a git hiccup: ask again (never changes what the test asserts).
        for attempt in range(3):
            out = self.watch("status")
            dirty = [ln for ln in git_retry(self.root, "status", "--porcelain").stdout.splitlines()
                     if ".brain" not in ln]
            if not dirty or "CHANGED since task start: 0 file(s)" not in out:
                return out
            time.sleep(0.3)
        return out

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
        self.watch("task", "X2", "ectd_engine/**", "tests/**")  # a NEW id: the same id would keep the original start
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

    def test_tests_summary_line_shown_when_output_follows_it(self):
        # an exit hook prints 30 lines AFTER unittest's summary, pushing it out of the last-20-lines tail
        late = "atexit.register(lambda: print(*['late'] * 30, sep=chr(10)))"
        self.write("tests/test_long.py", "import atexit, unittest\n\n" + late + "\n\n\nclass L(unittest.TestCase):\n"
                   "    def test_long(self):\n        self.fail('planted')\n")
        out = self.watch("status", "--tests")
        self.assertRegex(out, r"Ran \d+ tests? in ")
        self.assertIn("FAILED", out)

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

    def test_variable_path_then_open_write_is_write_evidence(self):
        self.dirty_a()
        self.log("Bash python -c \"X='ectd_engine/facts/a.py'; s=open(X).read(); open(X,'w').write(s)\"")
        self.assertNotIn("no logged action", self.status())

    def test_variable_path_then_write_text_is_write_evidence(self):
        self.dirty_a()
        self.log("Bash python -c \"p='ectd_engine/facts/a.py'; p.write_text('x')\"")
        self.assertNotIn("no logged action", self.status())

    def test_variable_path_only_read_is_not_write_evidence(self):
        self.dirty_a()
        self.log("Bash python -c \"X='ectd_engine/facts/a.py'; print(open(X).read()); open(X,'r').close()\"")
        self.assertIn("no logged action: ectd_engine/facts/a.py", self.status())

    def test_variable_for_another_file_is_not_write_evidence(self):
        self.dirty_a()
        self.log("Bash python -c \"X='ectd_engine/facts/a.py'; Y='other.txt'; open(Y,'w').write('x')\"")
        self.assertIn("no logged action: ectd_engine/facts/a.py", self.status())

    def test_same_task_id_again_keeps_original_start(self):
        task = self.root / ".brain" / "task.json"
        before = json.loads(task.read_text(encoding="utf-8"))
        before["started"] = "2020-01-01T00:00:00"
        task.write_text(json.dumps(before), encoding="utf-8")
        self.watch("task", "X", "ectd_engine/**")
        after = json.loads(task.read_text(encoding="utf-8"))
        self.assertEqual(after["started"], "2020-01-01T00:00:00")
        self.assertEqual(after["start_head"], before["start_head"])
        self.assertEqual(after["allowed"], ["ectd_engine/**"])  # the new allowed list still applies

    def test_different_task_id_gets_a_new_start(self):
        task = self.root / ".brain" / "task.json"
        before = json.loads(task.read_text(encoding="utf-8"))
        before["started"] = "2020-01-01T00:00:00"
        task.write_text(json.dumps(before), encoding="utf-8")
        self.watch("task", "Y", "tests/**")
        self.assertNotEqual(json.loads(task.read_text(encoding="utf-8"))["started"], "2020-01-01T00:00:00")

    def test_clean_change_raises_no_flag(self):
        self.append("ectd_engine/facts/a.py", "Z = 2\n")
        self.append("tests/test_a.py", "\n    def test_two(self):\n        self.assertEqual(2, 2)\n")
        self.assertIn("FLAGS: none", self.status())


class GitRetryTests(unittest.TestCase):
    """The repo-building helper survives one failed git call, and still fails loudly if git keeps failing."""

    def fake(self, fail_first):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            bad = len(calls) <= fail_first
            return subprocess.CompletedProcess(cmd, 128 if bad else 0, "", "fatal: planted" if bad else "")
        return run, calls

    def test_one_failure_then_success_builds_the_repo(self):
        run, calls = self.fake(fail_first=1)
        build_repo("x", run=run, pause=0)
        self.assertEqual(len(calls), 7)  # init failed once and was repeated, then 5 more steps ran
        self.assertEqual(calls[0], calls[1])

    def test_windows_refusing_to_start_git_is_retried(self):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            if len(calls) == 1:
                raise PermissionError("[WinError 5] Access is denied")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        git_retry("x", "init", run=run, pause=0)
        self.assertEqual(len(calls), 2)

    def test_always_failing_git_raises_with_git_message(self):
        run, calls = self.fake(fail_first=99)
        with self.assertRaises(RuntimeError) as cm:
            build_repo("x", run=run, pause=0)
        self.assertIn("planted", str(cm.exception))
        self.assertEqual(len(calls), 3)

    def test_status_asks_again_when_watcher_wrongly_says_zero_changes(self):
        class Fake(WatchFlagTests):
            calls = 0

            def watch(self, *args):
                Fake.calls += 1
                return ("CHANGED since task start: 0 file(s)\n" if Fake.calls == 1
                        else "CHANGED since task start: 1 file(s)\n")
        t = Fake("test_clean_change_raises_no_flag")
        t.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t.root, True)
        (t.root / "f.txt").write_text("x", encoding="utf-8")
        build_repo(t.root)
        (t.root / "f.txt").write_text("changed", encoding="utf-8")
        self.assertIn("1 file(s)", t.status())
        self.assertEqual(Fake.calls, 2)

    def test_real_repo_has_base_commit_and_local_author(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "f.txt").write_text("x", encoding="utf-8")
            build_repo(d)
            out = git_retry(d, "log", "-1", "--format=%an %s").stdout.strip()
            self.assertEqual(out, "t base")


class GitFailureTests(unittest.TestCase):
    """T-036: if git fails, the watcher must say so (exit 2) - never print 'FLAGS: none' on a failed look."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "f.txt").write_text("x", encoding="utf-8")
        build_repo(self.root)

    def load(self):
        """Load a fresh copy of tools/watch.py that looks at self.root, with no waiting between git tries."""
        import importlib.util
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        self.addCleanup(os.environ.pop, "CLAUDE_PROJECT_DIR", None)
        spec = importlib.util.spec_from_file_location("watch_under_test", WATCH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.GIT_PAUSE = 0
        return mod

    def status_with(self, fake, *args):
        """Run watch.status in-process with subprocess.run replaced by `fake`; return (exit code, printed text)."""
        import contextlib
        import io
        mod = self.load()
        real = subprocess.run
        buf = io.StringIO()
        mod.subprocess = type("S", (), {"run": staticmethod(lambda cmd, **kw: fake(real, cmd, **kw)),
                                         "SubprocessError": subprocess.SubprocessError,
                                         "TimeoutExpired": subprocess.TimeoutExpired,
                                         "Popen": subprocess.Popen, "PIPE": subprocess.PIPE,
                                         "STDOUT": subprocess.STDOUT})
        with contextlib.redirect_stdout(buf):
            code = mod.cmd_status(list(args))
        return code, buf.getvalue()

    @staticmethod
    def bad(cmd):
        return subprocess.CompletedProcess(cmd, 128, "", "fatal: planted failure")

    def test_always_failing_git_is_an_error_not_green(self):
        code, text = self.status_with(lambda real, cmd, **kw: self.bad(cmd))
        self.assertEqual(code, 2)
        self.assertIn("GIT ERROR: git ", text)
        self.assertIn("planted failure", text)
        self.assertIn("git failed - result unknown", text)
        self.assertNotIn("FLAGS: none", text)
        self.assertNotIn("CHANGED since", text)

    def test_git_that_cannot_start_is_an_error_not_green(self):
        def fake(real, cmd, **kw):
            raise PermissionError("[WinError 5] Access is denied")
        code, text = self.status_with(fake)
        self.assertEqual(code, 2)
        self.assertIn("GIT ERROR", text)
        self.assertNotIn("FLAGS: none", text)

    def test_only_the_diff_call_failing_is_still_an_error(self):
        # the old code turned exactly this into '0 file(s)' and 'FLAGS: none'
        (self.root / "f.txt").write_text("changed", encoding="utf-8")
        calls = []

        def fake(real, cmd, **kw):
            calls.append(cmd)
            return self.bad(cmd) if "diff" in cmd else real(cmd, **kw)
        code, text = self.status_with(fake)
        self.assertEqual(code, 2)
        self.assertIn("GIT ERROR: git diff", text)
        self.assertNotIn("FLAGS: none", text)
        self.assertGreaterEqual(sum("diff" in c for c in calls), 3)  # it tried 3 times

    def test_one_failure_then_success_gives_the_normal_result(self):
        (self.root / "f.txt").write_text("changed", encoding="utf-8")
        state = {"n": 0}

        def fake(real, cmd, **kw):
            state["n"] += 1
            return self.bad(cmd) if state["n"] == 1 else real(cmd, **kw)
        code, text = self.status_with(fake)
        self.assertEqual(code, 0)
        self.assertNotIn("GIT ERROR", text)
        self.assertIn("1 file(s)", text)
        self.assertIn("M f.txt", text)

    def test_real_repo_clean_is_unchanged_behaviour(self):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.root))
        r = run_retry([sys.executable, str(WATCH), "status"], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0)
        self.assertIn("CHANGED since HEAD: 0 file(s)", r.stdout)
        self.assertIn("FLAGS: none", r.stdout)
        self.assertNotIn("GIT ERROR", r.stdout)

    def test_repo_with_no_commits_is_not_an_error(self):
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, empty, True)
        git_retry(empty, "init", "-q")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(empty))
        r = run_retry([sys.executable, str(WATCH), "status"], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0)
        self.assertIn("no commits yet", r.stdout)
        self.assertNotIn("GIT ERROR", r.stdout)

    def test_folder_that_is_not_a_repo_is_not_an_error(self):
        plain = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plain, True)
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(plain), GIT_CEILING_DIRECTORIES=str(plain.parent))
        r = run_retry([sys.executable, str(WATCH), "status"], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0)
        self.assertIn("no repository yet", r.stdout)

    def test_task_command_reports_git_error(self):
        mod = self.load()
        import contextlib
        import io
        mod.subprocess = type("S", (), {"run": staticmethod(lambda cmd, **kw: self.bad(cmd)),
                                         "SubprocessError": subprocess.SubprocessError})
        buf = io.StringIO()
        old_argv = sys.argv
        sys.argv = ["watch.py", "task", "T-x"]
        try:
            with contextlib.redirect_stdout(buf):
                code = mod.main()
        finally:
            sys.argv = old_argv
        self.assertEqual(code, 2)
        self.assertIn("GIT ERROR", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
