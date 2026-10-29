# LEARN T-020 - Exact maths for the numbers in the dossier
Built: a small module that works out mean, spread (SD) and %RSD with exact decimal numbers, and rounds the way a dossier expects.
It is checked against five public NIST reference files whose right answers are known.
Why this way: we use Decimal, not float. Floats store 0.125 slightly wrong and Python round() gives 0.12; a dossier needs 0.13.
We did NOT use Python's statistics module: it hides how it rounds, so we could not prove it.
New words: Decimal = exact base-10 number type; ROUND_HALF_UP = 0.5 always goes up; SD = how spread out values are; %RSD = SD divided by mean, times 100
Look at: ectd_engine/stats/basic.py - conforms() rounds to the limit's own decimals BEFORE comparing.
Try it: python -m unittest tests.test_stats_basic -v - you should see 6 tests OK.
Remember: round first to the spec's decimals, then compare, and never let a float near a number.
