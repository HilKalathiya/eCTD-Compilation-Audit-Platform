# LEARN T-070 - Tests must not borrow the outside world
Built: The watch tests now start every child program with a clean environment (no inherited git settings) and restore what they change.
The cross-check now exits with 2 and writes a reason file when it cannot run, so it never fails silently.
Why this way: We did NOT add retries or longer waits. A test that only passes on the second try hides a real problem.
We proved one real leak first: with GIT_INDEX_FILE set, 19 of 46 watch tests failed and another repo's index was written.
New words: environment variable = a setting a program inherits from its parent; isolation = a test uses only its own temp folders; exit code 2 = "could not run", different from 1 = "found a mismatch".
Look at: tests/test_watch.py clean_env - it drops every GIT_* variable before a test runs git.
Try it: python -m unittest tests.test_watch_isolation - it should say OK (runs the watch tests with poisoned git settings and a fake live task).
Remember: If a test can be changed by where it is run from, it is not a test yet.
