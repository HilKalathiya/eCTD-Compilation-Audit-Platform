# LEARN K2 - Live gauges at the bottom of Claude Code
Built: a tiny script that prints task id, context %, cost and 5-hour limit % on one line.
Claude Code runs it after every reply and shows what it prints.
Why this way: a script reading JSON that Claude Code hands it. We did NOT choose a command
(like /usage) because you forget to run it; the line is always on screen.
New words: status line = the bar at the bottom; stdin = text piped into a program; JSON = labelled data
Look at: tools/statusline.py - every missing value prints "-" instead of crashing.
Try it: echo {} | python tools/statusline.py - shows "K2 | ctx - | cost - | 5h -"
Remember: a gauge you can always see beats a command you forget to run.
