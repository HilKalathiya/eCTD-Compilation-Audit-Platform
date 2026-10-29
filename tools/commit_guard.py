"""commit_guard.py - Stop hook: Claude Code may not finish a turn with work that is not on GitHub.

Claude Code runs this when it is about to stop (see .claude/settings.json). If the project has
uncommitted changes, or commits that are not pushed to origin yet, it answers "block" with a
reason, so Claude Code commits and pushes first. It blocks once per stop: when Claude Code tries
to stop again right after (stop_hook_active), it lets it go, so it can never loop forever.

Manual check:  python tools/commit_guard.py < nul      (Windows; prints nothing when all is pushed)
Standard library only. Output is built with json.dumps, never by hand.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent).resolve()


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout.strip()


def problems():
    """Return a list of plain-English problems; empty means everything is committed and pushed."""
    found = []
    code, dirty = git("status", "--porcelain")
    if code != 0:
        return []  # not a git repo, or git missing: nothing to guard
    if dirty:
        n = len(dirty.splitlines())
        found.append(f"{n} file(s) changed but not committed")
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
        reason = ("Project rule: commit and push to GitHub after every task. Not done yet: "
                  + "; ".join(found) + ". Run git add -A, git commit -m \"<task id>: <title>\", git push. "
                  "Hil is the only author: no Co-Authored-By or Claude lines in the message. "
                  "If these changes must not be committed, say why to Hil instead.")
        sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
