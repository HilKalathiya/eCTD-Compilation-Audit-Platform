# LEARN T-003 - Testing the last 3 alarms
Built: Three more tests that make a deliberate mistake in a throw-away copy of the project
and check that the watch tool shouts about it. Now every alarm has been heard ringing once.
Why this way: Each test builds its own temporary git repo, so nothing real is touched.
We did NOT just read the alarm code and trust it; an untested alarm may be silent.
New words: planted mistake = an error we put in on purpose to see if it gets caught
Look at: tests/test_watch.py - test_assertions_weakened first saves a 3-check test, then strips it
Try it: python -m unittest discover tests - should end with "Ran 13 tests ... OK"
Remember: A check you have never seen fail is a check you cannot trust.
