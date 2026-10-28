# LEARN T-002 - Test the alarm bell
Built: tests/test_watch.py plants 8 mistakes in a throwaway copy of a project and checks the watch tool rings the right alarm for each.
It also checks a clean change rings nothing.
Why this way: We test in a temporary git repo (not the real project) so the real task file and files are never touched.
We did NOT edit watch.py to make tests pass; an alarm that fails to ring must be reported, not hidden.
New words: temp repo = a short-lived scratch git folder deleted after the test; subprocess = running another program from Python;
false alarm = a warning that fires when nothing is wrong.
Look at: tests/test_watch.py - setUp builds the scratch repo; each test plants exactly one mistake.
Try it: python -m unittest tests.test_watch -v - you should see 9 tests, all ok.
Remember: A check you have never seen fail is a check you cannot trust.
