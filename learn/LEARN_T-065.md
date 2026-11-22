# LEARN T-065 - Testing the writer on data it never saw
Built: 20 made-up stability cases (8 with results outside the limit) that the writer was never tuned on, run twice (direct and as a skill), plus a retry test and a blind sheet for you.
Why this way: Code makes the test data from a written rule, so nobody can quietly shape it to fit the prompt. We did NOT reuse the old tuning data, because passing on data you tuned on proves little.
New words: held-out = test data kept away from tuning; planted error = a mistake we add on purpose to see if a check catches it; blind sheet = answers hidden so you judge without hints.
Look at: ectd_engine/stability/heldout.py - the rule is written in the top docstring.
Try it: python -m ectd_engine.stability.heldout --out heldout_copy.csv - prints "114 rows written ... 8 with results outside the limit".
Remember: A check you never saw fail is a check you cannot trust; the planted errors show it can fail.
