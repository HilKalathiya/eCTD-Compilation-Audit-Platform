"""commit_guard.py - Stop hook: Claude Code may not finish a TASK with work that is not on GitHub.

Claude Code runs this when it is about to stop (see .claude/settings.json). Every task ends by
updating STATE.md (CLAUDE.md step 8), so a changed STATE.md means "task finished". It answers
"block" with a reason only when (a) STATE.md is changed but not committed, or (b) there are
commits not pushed to origin yet. Other uncommitted files (for example the log of a long job that
is still running) are left alone, so ordinary turns in the middle of a task are not blocked.
It blocks once per stop: when Claude Code tries to stop again right after (stop_hook_active),
it lets it go, so it can never loop forever.

Manual check:  python tools/commit_guard.py < nul      (Windows; prints nothing when all is pushed)
Standard library only. Output is built with json.dumps, never by hand.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent).resolve()


def find_git():
    """git.exe is not always on the PATH Claude Code gives hooks on Windows, so also look in the usual places."""
    found = shutil.which("git")
    if found:
        return found
    places = []
    bash = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")  # Claude Code on Windows: ...\Git\bin\bash.exe
    if bash:
        places.append(Path(bash).parent / "git.exe")
    for base in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if os.environ.get(base):
            root = Path(os.environ[base]) / ("Programs" if base == "LOCALAPPDATA" else "") / "Git"
            places += [root / "cmd" / "git.exe", root / "bin" / "git.exe"]
    return next((str(p) for p in places if p.is_file()), None)


def git(*args):
    exe = find_git()
    if not exe:
        return 127, ""
    try:
        r = subprocess.run([exe, "-c", "safe.directory=*", *args], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return r.returncode, r.stdout.strip()


def problems():
    """Return a list of plain-English problems; empty means everything is committed and pushed."""
    found = []
    code, dirty = git("status", "--porcelain")
    if code != 0:
        return []  # not a git repo, or git missing: nothing to guard, never crash
    lines = dirty.splitlines()
    # "XY path" (or "R  old -> new"); split on whitespace because git() strips the first line's leading space
    paths = [line.split(None, 1)[-1].split(" -> ")[-1].strip('"') for line in lines]
    if "STATE.md" in paths:  # the task is finished (STATE.md updated) but its work is not committed
        found.append(f"task finished (STATE.md updated) but {len(lines)} file(s) changed and not committed")
    code, ahead = git("rev-list", "--count", "@{u}..HEAD")
    if code != 0:
        found.append("this branch has no upstream on GitHub yet (use git push -u origin <branch>)")
    elif ahead.isdigit() and int(ahead) > 0:
        found.append(f"{ahead} commit(s) not pushed to GitHub")
    return found


def main():
    try:
        d = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        d = {}
    if d.get("stop_hook_active"):
        return 0  # already reminded once this stop; never block twice
    found = problems()
    if found:
        reason = ("Project rule: commit and push to GitHub once at the end of every task. Not done yet: "
                  + "; ".join(found) + ". Commit and push now: git add the task's files, git commit -m \"<task id>: <title>\", git push. "
                  "Hil is the only author: no Co-Authored-By or Claude lines in the message. "
                  "If these changes must not be committed, say why to Hil instead.")
        sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
