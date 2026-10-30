# LEARN T-024 - Asking someone else's code to check ours
Built: a test that gives the same stability data to R's expirest package and to our code, and compares shelf life and pooling decision.
A second test checks our straight-line fit against NIST's certified Norris answers.
Why this way: we use R as an outside witness; the alternative, re-checking with our own code again, would repeat any mistake we made.
We also ran the whole suite 6 times to find tests that pass only sometimes: none did.
New words: expirest = R package that computes shelf life the ICH Q1E way; certified value = answer NIST proved correct; flaky test = a test that passes and fails at random
Look at: tests/test_r_crosscheck.py - the missing-R test FAILS with "install R" instead of skipping.
Try it: python -m unittest tests.test_r_crosscheck -v - you should see 9 tests OK.
Remember: a check only counts when code written by someone else agrees.
