# LEARN K4 - Making Claude talk in plain words
Built: A tiny "Plain words" output style file, switched on in `.claude/settings.json`, so every reply is short and beginner friendly.
Why this way: CLAUDE.md holds project facts, a style holds how Claude talks, a hook forces things to always happen. We did NOT put the talking rules in CLAUDE.md, because it is already long and mixes two jobs.
New words: output style = a saved set of talking rules; frontmatter = the settings lines at the top of a file.
Look at: .claude/output-styles/plain-words.md - the name must match settings.json exactly, including capital letters.
Try it: python -m unittest tests.test_output_style - 7 tests OK.
Remember: the style is sent every turn, so each extra line costs tokens every time.
