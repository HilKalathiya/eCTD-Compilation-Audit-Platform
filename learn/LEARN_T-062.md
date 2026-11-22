# LEARN T-062 - Stability facts: real where public, labelled demo where hidden
Built: A table of stability numbers (data/stability/finerenone_stability.csv) and code that counts, min/max and last value per condition and test.
Only 4 rows are real (shelf life 36 months, how long each storage condition was studied). 60 rows are demo values.
Why this way: The FDA review blacks out all stability results, so real numbers do not exist in public. We did NOT fill them in as "real"; every demo row says DEMO in its source, and the code rejects a demo row dressed as public.
Demo rule (all values stay inside the demo limit; value = start - rate x month):
 - Assay (limit 95.0-105.0 %): 100.00 - k*m, k = 0.02 (25C/60%RH), 0.03 (30C/75%RH), 0.10 (40C/75%RH)
 - Degradation product (limit NMT 0.50 %): 0.050 + k*m, k = 0.002, 0.004, 0.020
 - Dissolution at 15 min (limit NLT 80 %): 96.00 - k*m, k = 0.03, 0.05, 0.15
 - Limits are demo too (the real ones are redacted). Months: 0,3,6,9,12,18,24,36 (long-term); 0,1,3,6 (accelerated).
New words: time point = one test date in a study; demo row = made-up row, clearly labelled; redacted = blacked out by FDA.
Look at: ectd_engine/stability/facts.py - check_rows() is the part that refuses mislabelled rows.
Try it: python -m unittest tests.test_stability_facts - you should see 16 tests, OK.
Remember: If a number is not public, say so in the label, never in a footnote.
