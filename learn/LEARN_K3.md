# LEARN K3 - A guard that stops edits to protected files
Built: `python tools/watch.py guard`, run by Claude Code BEFORE every Edit/Write. If the file is protected
(frozen) and the current task does not list it, the edit is refused with a reason.
Why this way: a rule in CLAUDE.md only asks; a hook is code that runs every time. We did NOT choose checking
afterwards (the old status flags) because by then the file is already changed.
New words: hook = a script Claude Code runs automatically at set moments; exit code 2 = "stop, do not do this"; PreToolUse = the moment just before a tool runs
Look at: tools/watch.py (cmd_guard) - it allows anything it does not understand, and blocks only on exit 2.
Try it: ask Claude Code "add a comment to writer_test/README.md" - it should be blocked with "BLOCKED by watch guard".
Remember: Bash writes (echo > file, sed -i) are NOT covered; the guard only sees Edit/Write/MultiEdit/NotebookEdit. Honest limit.
