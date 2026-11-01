# LEARN K7 - a cheap helper that runs the tests for us
Built: A small helper called test-runner. It runs the tests and tells the main chat only the verdict, in 10 lines or less.
A test file checks that the helper can only run commands and read, never change files.
Why this way: We could have run the tests in the main chat, but hundreds of output lines would fill it and cost more every turn.
We did NOT give the helper Edit or Write, so even if it goes wrong it cannot change your code.
New words: subagent = a small helper with its own chat; haiku = the smallest, cheapest model; frontmatter = the settings block at the top of a file
Look at: .claude/agents/test-runner.md - the "tools:" line lists only Bash and Read.
Try it: python -m unittest tests.test_agents - 6 tests pass.
Remember: A helper that cannot write cannot break anything.
