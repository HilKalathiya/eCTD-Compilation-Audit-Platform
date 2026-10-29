# LEARN T-008 - Plugging three leaks in the Fact box
Built: The Fact box now refuses an empty batch or condition, odd-looking number text, and unknown extra fields in saved JSON.
Also closed the round-3 audit counts for the writer test.
Why this way: Strict "allow only this exact shape" rules, not "clean it up quietly" (like trimming spaces): cleaning would hide a bad source.
Literal "n/a" marks "no batch" so a blank can never mean "forgot".
New words: regex = a pattern that text must match exactly; whitelist = only listed things are allowed
Look at: ectd_engine/facts/schema.py - _VALUE_RE and _KEYS near the top, used in from_json.
Try it: python -m unittest tests.test_fact_schema -v - you should see 30 tests, all ok.
Remember: If a rule can say no, it should say no loudly.
