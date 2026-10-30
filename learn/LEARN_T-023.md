# LEARN T-023 - Spotting an odd new result, and handling "<LOQ"
Built: a check that says if a new stability result sits outside the range earlier points predict. Plus rules for results too small to measure ("<LOQ").
Why this way: the range is a prediction interval (where ONE new result should land), not the confidence bound (where the average line is).
The bound is too narrow and would flag normal scatter. We did NOT turn "<LOQ" into 0 or LOQ/2: that would change shelf life silently.
Default is to leave those points out and say so in a note.
New words: prediction interval = range where a single new result is expected; OOT = out of trend; LOQ = smallest amount the method can measure; ND = not detected.
Look at: ectd_engine/stats/loq.py - SUBSTITUTE refuses to run without a value AND a written reason.
Try it: python -m unittest tests.test_oot_loq -v - 22 tests, all ok.
Remember: a result can pass the specification and still be out of trend.
