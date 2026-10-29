# LEARN T-012 - Range double check compares numbers, not spelling
Built: The gate now reads both range files as numbers and compares those. "1" and "1.0" count as the same limit.
Different numbers, an extra test name, or text like "abc" still stop the gate from loading.
Why this way: We could have kept comparing the raw text and asked Hil to copy every digit exactly. We did not: that fails on harmless spelling and teaches nothing.
We used Decimal (exact numbers), not float, so 0.1 stays exactly 0.1.
New words: Decimal = exact base-10 number type; planted error = a deliberate mistake that proves a check can fail.
Look at: ectd_engine/gate/gate.py - range_limits() turns each file into {test: (min, max)} before the compare.
Try it: python -m unittest tests.test_gate -v - the 4 new range tests (same number, close number, extra name, "abc") all say ok.
Remember: Compare what a value means, not how it was typed.
