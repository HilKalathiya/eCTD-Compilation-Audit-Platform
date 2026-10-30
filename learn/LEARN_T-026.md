# LEARN T-026 - Database setup that runs each step only once
Built: `migrate` now keeps a list of the setup files it already ran. Running it again skips them.
Why this way: We could have rewritten old files to be safe to repeat; we did not because edited history is risky.
A saved fingerprint (sha256) catches any file changed after it ran.
New words: migration = a numbered file that changes the database; sha256 = a fingerprint of a file's text
Look at: ectd_engine/db/migrate.py - the `done` list and the "edited after it ran" error
Try it: python -m unittest tests.test_migrate - 3 tests pass (needs Docker running)
Remember: Setup steps are history; run each once and never rewrite them.
