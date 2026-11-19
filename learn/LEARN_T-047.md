# LEARN T-047 - Test the P.5.6 writer with the real model, and test the human too
Built: A runner that makes 130 random batch windows, and an audit tool that re-reads every accepted paragraph. It also builds a 25-row sheet with 3 deliberately wrong rows.
Why this way: A human check only counts if it is shown it can fail, so 3 planted wrong rows are hidden in the sheet. We did NOT just trust Hil's labels, as in P.5.4, because 25 "right" labels would also come from someone not looking.
Result: Gemma got 0/130 accepted: it writes 2 sentences when no batch is outside the limit, and the checker wants 3. We did not loosen the checker; the brain decides.
New words: planted row = a wrong row we add on purpose; window = a random group of batches
Look at: tools/audit_p56.py - function plant() makes the wrong copies and refuses if the re-read would not catch them
Try it: python -m unittest tests.test_audit_p56 - should print "Ran 15 tests ... OK"
Remember: A check that cannot fail proves nothing.
