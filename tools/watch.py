"""watch.py - lets the BRAIN see what the HANDS (Claude Code) are doing, in few tokens.

Commands (run from the project root, plain Python 3.8+, standard library only):
  python tools/watch.py status            compact dashboard (<= ~45 lines): task, git, activity, FLAGS
  python tools/watch.py status --tests    same, plus runs the unit tests in tests/
  python tools/watch.py run "<command>"   run a command (e.g. an ACCEPT line), print EXIT code + last 20 lines
  python tools/watch.py task T-002 "ectd_engine/facts/**" "tests/**"   start a task: id + allowed paths
  python tools/watch.py task clear        clear the current task
  python tools/watch.py log               hook entry point (reads Claude Code hook JSON on stdin)
  python tools/watch.py guard             PreToolUse hook: exit 2 blocks Edit/Write on a frozen path the task does not allow
  python tools/watch.py now [N]           the last N actions in PLAIN ENGLISH (for a human, default 15)
  python tools/watch.py live              live feed in plain English; keep it open in a second terminal (Ctrl+C stops)

Windows: python tools/watch.py status | clip     (copies the dashboard; paste it into the brain chat)
Output is ASCII only so it survives clipboards and consoles.
"""
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent).resolve()
BRAIN = ROOT / ".brain"
ACTIVITY = BRAIN / "activity.log"
TASK = BRAIN / "task.json"

FROZEN = ["writer_test/", "checks_stress_test/", "ocr_stress_test/", "handoff/", "Laboratory.csv",
          "Claude outputs/", "Life Sciences & Pharmaceutical R&D/", "tools/watch.py", ".claude/"]
ALWAYS_OK = ["STATE.md", ".brain/", ".gitignore", "learn/"]
STRICT_DIRS = ("ectd_engine/facts/", "ectd_engine/writer/", "ectd_engine/validator/", "ectd_engine/ledger/")


def out(text=""):
    sys.stdout.write(str(text).encode("ascii", "replace").decode("ascii") + "\n")


def git(*args, check=False):
    try:
        r = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(ROOT), *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None if check else r.stdout
    return r.stdout


def is_repo():
    return git("rev-parse", "--is-inside-work-tree", check=True) is not None


# ---------------------------------------------------------------- log (hook)
def cmd_log():
    try:
        d = json.loads(sys.stdin.read() or "{}")
        ev = d.get("hook_event_name", "?")
        if ev == "Stop":
            line = "STOP (turn finished)"
        else:
            tool = d.get("tool_name", "?")
            ti = d.get("tool_input") or {}
            target = ti.get("file_path") or ti.get("command") or ti.get("pattern") or ti.get("path") or ""
            target = re.sub(r"\s+", " ", str(target)).strip()
            try:
                target = os.path.relpath(target, ROOT).replace("\\", "/") if os.path.isabs(target) else target
            except ValueError:
                pass
            line = f"{tool} {target[:110]}"
        BRAIN.mkdir(exist_ok=True)
        with open(ACTIVITY, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + line + "\n")
        if ACTIVITY.stat().st_size > 300_000:
            lines = ACTIVITY.read_text(encoding="utf-8", errors="replace").splitlines()[-1000:]
            ACTIVITY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass  # a logging hook must never disturb the work
    return 0


# ---------------------------------------------------------------- task
def cmd_task(args):
    BRAIN.mkdir(exist_ok=True)
    if not args or args[0] == "clear":
        if TASK.exists():
            TASK.unlink()
        out("task cleared")
        return 0
    head = (git("rev-parse", "HEAD", check=True) or "").strip() or None
    data = {"id": args[0], "allowed": args[1:], "start_head": head, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    TASK.write_text(json.dumps(data, indent=1), encoding="utf-8")
    out(f"task {args[0]} started; allowed={args[1:] or 'ANY'}; base={head[:8] if head else 'no commits'}")
    return 0


def load_task():
    try:
        return json.loads(TASK.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------- run
def cmd_run(args):
    if not args:
        out("usage: watch.py run \"<command>\"")
        return 2
    t0 = time.time()
    try:
        r = subprocess.run(args[0], shell=True, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        text = (r.stdout or "") + (r.stderr or "")
        code = r.returncode
    except subprocess.TimeoutExpired:
        text, code = "TIMEOUT after 300 s", 124
    tail = text.strip().splitlines()[-20:]
    out(f"EXIT {code}  ({time.time() - t0:.1f}s)  $ {args[0][:100]}")
    for ln in tail:
        out("  " + ln[:160])
    return 0


# ---------------------------------------------------------------- guard (PreToolUse hook)
GUARDED_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def cmd_guard():
    """Read hook JSON on stdin; exit 2 (block) only for a frozen path the current task does not allow."""
    try:
        data = json.loads(sys.stdin.read())
        if data.get("tool_name") not in GUARDED_TOOLS:
            return 0
        ti = data.get("tool_input") or {}
        raw = ti.get("file_path") or ti.get("notebook_path")
        if not raw:
            return 0
        p = Path(raw)
        rel = (p if p.is_absolute() else ROOT / p).resolve().relative_to(ROOT).as_posix()
    except Exception:
        return 0
    if not any(rel.startswith(fz) or rel == fz for fz in FROZEN):
        return 0
    task = load_task()
    allowed = (task or {}).get("allowed") or []
    if any(matches(rel, a) for a in allowed):
        return 0
    why = f"task {task['id']} does not allow it" if task else "no task is active"
    sys.stderr.write(f"BLOCKED by watch guard: {rel} is a FROZEN path and {why}. "
                     "Ask the brain for a TASK CARD that lists this path.\n")
    return 2


# ---------------------------------------------------------------- guard flags
def matches(path, pattern):
    pattern = pattern.replace("\\", "/")
    if pattern.endswith("/**") or pattern.endswith("/"):
        return path.startswith(pattern.rstrip("*"))
    return fnmatch.fnmatch(path, pattern) or path == pattern


def changed_files(base):
    """(status, path) for tracked changes since base (or HEAD) plus untracked files."""
    res = {}
    diff = git("diff", "--name-status", base or "HEAD") if (base or git("rev-parse", "HEAD", check=True)) else ""
    for ln in (diff or "").splitlines():
        parts = ln.split("\t")
        if len(parts) >= 2:
            res[parts[-1].replace("\\", "/")] = parts[0][0]
    for p in (git("ls-files", "--others", "--exclude-standard") or "").splitlines():
        res[p.replace("\\", "/")] = "?"
    return {p: s for p, s in res.items() if not p.startswith(".brain/")}


def added_removed(base, pathspec=None):
    args = ["diff", "--unified=0", base or "HEAD"]
    if pathspec:
        args += ["--", *pathspec]
    text = git(*args) or ""
    cur, added, removed = None, {}, {}
    for ln in text.splitlines():
        if ln.startswith("+++ "):
            cur = ln[6:].strip() if ln.startswith("+++ b/") else None
        elif cur and ln.startswith("+") and not ln.startswith("+++"):
            added.setdefault(cur, []).append(ln[1:])
        elif cur and ln.startswith("-") and not ln.startswith("---"):
            removed.setdefault(cur, []).append(ln[1:])
    return added, removed


def untracked_lines(paths):
    res = {}
    for p in paths:
        f = ROOT / p
        try:
            if f.is_file() and f.stat().st_size < 400_000 and f.suffix in {".py", ".txt", ".md", ".json"}:
                res[p] = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    return res


def flags(task, changed):
    fl = []
    base = (task or {}).get("start_head")
    allowed = (task or {}).get("allowed") or []
    paths = sorted(changed)
    # 1 frozen folders
    for p in paths:
        if any(p.startswith(fz) or p == fz for fz in FROZEN) and not any(matches(p, a) for a in allowed):
            fl.append(f"FROZEN path touched: {p}")
    # 2 out-of-scope
    if allowed:
        for p in paths:
            if not any(matches(p, a) for a in allowed) and not any(matches(p, a) for a in ALWAYS_OK) \
                    and not any(p.startswith(fz) for fz in FROZEN):
                fl.append(f"outside task scope: {p}")
    added, removed = added_removed(base)
    ut = [p for p, s in changed.items() if s == "?"]
    for p, lines in untracked_lines(ut).items():
        added.setdefault(p, []).extend(lines)
    is_test = lambda p: "/tests/" in "/" + p or os.path.basename(p).startswith("test_")
    # 3 deleted tests / weakened tests
    rem_tests = {m.group(1) for p, ls in removed.items() if is_test(p) for l in ls
                 for m in [re.match(r"\s*(?:async\s+)?def (test\w*)", l)] if m}
    add_tests = {m.group(1) for p, ls in added.items() if is_test(p) for l in ls
                 for m in [re.match(r"\s*(?:async\s+)?def (test\w*)", l)] if m}
    gone = sorted(rem_tests - add_tests)
    if gone:
        fl.append(f"TESTS REMOVED ({len(gone)}): {', '.join(gone[:4])}")
    skips = [l.strip() for p, ls in added.items() if is_test(p) for l in ls
             if re.search(r"unittest\.skip|skipIf|skipUnless|mark\.skip|xfail|expectedFailure", l)]
    if skips:
        fl.append(f"skip/xfail ADDED in tests ({len(skips)}): {skips[0][:60]}")
    a_assert = sum(1 for p, ls in added.items() if is_test(p) for l in ls if re.search(r"\bassert\w*\b", l))
    r_assert = sum(1 for p, ls in removed.items() if is_test(p) for l in ls if re.search(r"\bassert\w*\b", l))
    if r_assert - a_assert >= 3:
        fl.append(f"assertions net -{r_assert - a_assert} in tests (weakened?)")
    # 4 project rules in engine code
    for p, ls in added.items():
        if not p.startswith("ectd_engine/") or is_test(p):
            continue
        if any(re.search(r"(?<![\w.])round\(", l) for l in ls):
            fl.append(f"round() used in {p} (rule: Decimal ROUND_HALF_UP)")
        if p.startswith(STRICT_DIRS) and any(re.search(r"\bfloat\(", l) for l in ls):
            fl.append(f"float() used in {p} (values must be Decimal)")
    for p, ls in added.items():
        if any(re.search(r"(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"\s]{8,}", l, re.I) for l in ls):
            fl.append(f"possible secret in {p}")
    # 5 hygiene
    if "requirements.txt" in changed:
        fl.append("requirements.txt changed (new dependency? must be in the report)")
    src = [p for p in paths if p.startswith("ectd_engine/") and p.endswith(".py") and not is_test(p)]
    if src and not any(is_test(p) for p in paths):
        fl.append("engine code changed but NO test file changed")
    for p in paths:
        try:
            if (ROOT / p).is_file() and (ROOT / p).stat().st_size > 1_000_000 and not p.startswith(tuple(FROZEN)):
                fl.append(f"large file (>1 MB): {p}")
        except OSError:
            pass
    return fl


# ---------------------------------------------------------------- plain English (for Hil)
BASH_RULES = [
    (r"unittest|pytest", "ran the tests (checks that the code still works)"),
    (r"git commit", "saved a snapshot of the code (git commit)"),
    (r"git init", "started version history for the project (git init)"),
    (r"git add", "picked files for the next snapshot (git add)"),
    (r"git (status|diff|log|show)", "looked at what changed (git)"),
    (r"(pip|npm) install", "installed a library"),
    (r"watch\.py task", "started the task and wrote down which files it may touch"),
    (r"watch\.py", "checked its own work with the watch tool"),
    (r"section\.py", "read one section of the explainer"),
    (r"ollama|writer_test", "ran the writer test with the local AI model"),
    (r"python3? -m ectd_engine|python3? ectd_engine", "ran our own program"),
    (r"^(ls|dir|cat|head|tail|grep|find|type|wc|rg)\b", "looked at files"),
    (r"^mkdir", "made a folder"),
]


def doc_of(rel):
    """First line of a python file's top docstring: what the file is for, in the author's words."""
    f = ROOT / rel
    try:
        if f.suffix == ".py" and f.is_file():
            m = re.search(r'^\s*(?:#[^\n]*\n\s*)*(?:"""|\'\'\')\s*([^\n]{3,90})', f.read_text(encoding="utf-8", errors="replace")[:800])
            if m:
                return m.group(1).strip().rstrip('"\'. ')
    except OSError:
        pass
    return ""


def plain(line):
    """'2026-10-28T09:41:02 Edit ectd_engine/x.py' -> '09:41  changed x.py - what it is for'."""
    hhmm = line[11:16]
    body = line[20:].strip() if len(line) > 20 else line
    tool, _, target = body.partition(" ")
    name = target.replace("\\", "/").split("/")[-1] or target
    d = doc_of(target) if tool in ("Edit", "MultiEdit", "Write", "Read") else ""
    tail = f" - {d}" if d else ""
    if body.startswith("STOP"):
        return f"{hhmm}  finished this step - waiting for you"
    if tool in ("Edit", "MultiEdit"):
        return f"{hhmm}  changed the file {name}{tail}"
    if tool == "Write":
        return f"{hhmm}  wrote the file {name}{tail}"
    if tool == "Read":
        return f"{hhmm}  read the file {name}{tail}"
    if tool in ("Grep", "Glob"):
        return f"{hhmm}  searched the files for: {target[:60]}"
    if tool == "Bash":
        for pat, text in BASH_RULES:
            if re.search(pat, target):
                extra = f": {target[:50]}" if "install" in text else ""
                return f"{hhmm}  {text}{extra}"
        return f"{hhmm}  ran a command: {target[:60]}"
    return f"{hhmm}  {body[:80]}"


def cmd_now(args):
    n = int(args[0]) if args and args[0].isdigit() else 15
    if not ACTIVITY.exists():
        out("nothing logged yet - Claude Code has not done anything since the hooks were installed")
        return 0
    for ln in ACTIVITY.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]:
        out(plain(ln))
    return 0


def cmd_live():
    out("LIVE FEED in plain English (Ctrl+C to stop). Waiting for Claude Code...")
    pos = ACTIVITY.stat().st_size if ACTIVITY.exists() else 0
    try:
        while True:
            if ACTIVITY.exists():
                size = ACTIVITY.stat().st_size
                if size < pos:
                    pos = 0
                if size > pos:
                    with open(ACTIVITY, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(pos)
                        for ln in f.read().splitlines():
                            out(plain(ln))
                        pos = f.tell()
                    sys.stdout.flush()
            time.sleep(1)
    except KeyboardInterrupt:
        out("stopped")
    return 0


# ---------------------------------------------------------------- status
def cmd_status(args):
    task = load_task()
    out(f"== BRAIN STATUS {time.strftime('%Y-%m-%d %H:%M')} ==")
    if task:
        out(f"TASK: {task['id']} started {task['started'][11:16]} allowed={task['allowed'] or 'ANY'}")
    else:
        out("TASK: none set (hands should run: python tools/watch.py task <id> <allowed paths>)")
    if not is_repo():
        out("GIT: no repository yet (T-001 not done)")
        changed = {}
    elif git("rev-parse", "HEAD", check=True) is None:
        out("GIT: repository has no commits yet (flags suspended until the first commit)")
        changed = {}
    else:
        branch = (git("rev-parse", "--abbrev-ref", "HEAD", check=True) or "?").strip()
        log = (git("log", "--oneline", "-5") or "").strip().splitlines()
        since = ""
        if task and task.get("start_head"):
            n = (git("rev-list", "--count", f"{task['start_head']}..HEAD") or "0").strip()
            since = f" | {n} commit(s) since task start"
        out(f"GIT: branch {branch}{since}")
        for ln in log:
            out("  " + ln[:100])
        changed = changed_files((task or {}).get("start_head"))
        out(f"CHANGED since {'task start' if task else 'HEAD'}: {len(changed)} file(s)")
        for p in sorted(changed)[:12]:
            out(f"  {changed[p]} {p}")
        if len(changed) > 12:
            out(f"  ... +{len(changed) - 12} more")
    if ACTIVITY.exists():
        lines = ACTIVITY.read_text(encoding="utf-8", errors="replace").splitlines()
        out(f"ACTIVITY (last 10 of {len(lines)}):")
        for ln in lines[-10:]:
            out("  " + ln[11:])
    else:
        out("ACTIVITY: no log yet (hooks not installed? see handoff/claude_settings.template.json)")
    fl = flags(task, changed) if changed else []
    out("FLAGS: " + ("none" if not fl else str(len(fl))))
    for f in fl[:12]:
        out("  ! " + f)
    if "--tests" in args:
        if (ROOT / "tests").is_dir():
            cmd_run(["python -m unittest discover tests"])
        else:
            out("TESTS: no tests/ folder yet")
    st = ROOT / "STATE.md"
    if st.exists():
        body = [l for l in st.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        out("STATE.md head: " + " | ".join(l.strip("-# ").strip()[:70] for l in body[1:4]))
    return 0


def main():
    a = sys.argv[1:]
    if not a:
        sys.stdout.write(__doc__)
        return 0
    cmd, rest = a[0], a[1:]
    if cmd == "log":
        return cmd_log()
    if cmd == "task":
        return cmd_task(rest)
    if cmd == "run":
        return cmd_run(rest)
    if cmd == "status":
        return cmd_status(rest)
    if cmd == "now":
        return cmd_now(rest)
    if cmd == "live":
        return cmd_live()
    if cmd == "guard":
        return cmd_guard()
    sys.stdout.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
