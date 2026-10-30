# LEARN K5 - Slash commands became skills, plus /verify
Built: /where, /explain, /recap now live in .claude/skills/ (same text as before). A new /verify runs the watch tool and reports in 3 lines.
Why this way: a skill costs only its one-line description until you call it, and can hold extra files. A command is the older form of the same thing.
We did NOT put this in CLAUDE.md: that file is read every session, so every line there costs tokens all the time.
New words: skill = a packaged instruction that loads only when called; frontmatter = the small settings block at the top of a file.
Look at: .claude/skills/verify/SKILL.md - allowed-tools lets it run only watch.py.
Try it: restart Claude Code, type / and look for where, explain, recap, verify - you should see all 4.
Remember: CLAUDE.md = always on, skill = on demand, command = old skill.
