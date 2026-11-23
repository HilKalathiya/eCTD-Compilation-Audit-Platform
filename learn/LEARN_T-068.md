# LEARN T-068 - Module 2.3 written by code, then checked by a second reader
Built: A short summary document (2.3) made only from stored facts, plus a separate checker that compares it with the full 3.2 text.
Every number in it points to a fact; the checker starts by assuming each number is wrong.
Why this way: The checker does NOT reuse the builder's data or code, because a checker that shares the builder's mistakes cannot catch them.
We also did NOT let the model write any number; code fills every value.
New words: crosscheck = a second, independent comparison; graph = the fact store (Neo4j); planted error = a mistake we add on purpose to see if the check fails.
Look at: evidence/T-068/run1/summary.md - 30 numbers in the web file and 30 in the Word file, all matched.
Try it: python -m unittest tests.test_crosscheck - it should say OK; each planted mistake must make the check FAIL.
Remember: A check you never saw fail is a check you cannot trust.
