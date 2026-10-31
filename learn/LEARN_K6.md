# LEARN K6 - Rules that load only when they matter
Built: A new file `.claude/rules/engine.md` holds the number rules for engine code.
CLAUDE.md now only points to it.
Why this way: A path-scoped rule loads only when Claude touches `ectd_engine/**`.
We did NOT keep it in CLAUDE.md, because that loads every turn, even for docs work, and costs tokens.
New words: path-scoped rule = a rule file that loads only for files matching a path pattern; frontmatter = the small settings block at the top of a file, between two --- lines.
Look at: .claude/rules/engine.md - the `paths:` block at the top.
Try it: python -m unittest tests.test_rules - you should see OK.
Remember: Put a rule only where it is needed, so every other turn stays cheap.
