# LEARN T-055 - Name the failing test, hunt the flaky one
Built: The test report now names each failing test and its last error line. The log hook no longer fails silently.
Why this way: One test failed once in 5 full runs and I could not make it fail again (540 tries). We did NOT add a retry or sleep: that would hide the bug. Instead we added a clue: the next failure prints the hook's exit code and error text.
New words: flaky test = a test that fails only sometimes; stderr = the error channel of a program.
Look at: tools/watch.py - failing_tests() reads unittest output and pairs names with errors.
Try it: python -m unittest tests.test_watch -k failing - 5 tests, OK.
Remember: A flaky test is not fixed until we know why it failed; one clean run proves nothing.
