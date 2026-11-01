# LEARN T-035 - Steadier watcher tests + clean reloads
Built: The watcher tests now build their throw-away git repos through one helper that tries again if git hiccups. Reloading a guideline now removes chunks that no longer exist.
Why this way: We did NOT just raise timeouts or skip the test; the real cause was a one-off git failure (exit 128) on Windows, so a short retry fixes it without weakening any check. For the database we did NOT delete a whole document first and re-add it; one transaction (all-or-nothing step) means a failed reload cannot leave the table half empty.
New words: retry = try the same step again after a short wait; transaction = a group of database steps that all happen or none do; stale row = a stored row whose source no longer exists
Look at: tests/test_watch.py - git_retry() and build_repo() at the top; ectd_engine/knowledge/load.py - store() and DELETE_STALE
Try it: python -m unittest tests.test_watch.GitRetryTests -v - 3 tests, all ok
Remember: A flaky test is a clue; find the real error before changing anything.
