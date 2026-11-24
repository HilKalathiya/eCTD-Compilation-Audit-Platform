# LEARN T-073 - Realistic test cases: a claim must agree with the data
Built: a limit is now stored once (the specification table) and read from there; "stability was demonstrated" and a longer shelf life are allowed only when the data support them.
New test cases mix good data, results outside the limit, and cases where extending the shelf life must be refused. A separate checker recomputes everything on its own.
Why this way: we did NOT keep the T-072 examples to get a high score; with no example Gemma scored 0/10, so we show the allowed wordings as patterns with blanks and say honestly that the copy rate after blanking is now high.
We also did NOT edit the old T-072 files; the new work sits beside them so the old tests still pin the old results.
New words: significant change = ICH test of an accelerated study; extrapolation = shelf life longer than the real data; data-src link = a mark naming the fact a sentence depends on.
Look at: ectd_engine/summary/m23_rules.py - the header names the ICH chunks each rule comes from; each rule has a planted test both ways.
Try it: python -m unittest tests.test_m23_v3_writer - it should say OK (bad data + the word "demonstrated" is rejected; the same words on clean data pass).
Also: tools/watch.py now logs tool calls that fail (FAILED ... [exit N]), so the activity log no longer misses them.
Remember: the checker must not share code with the thing it checks, and a held-out score only counts if the files were frozen first.
