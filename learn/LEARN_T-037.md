# LEARN T-037 - Thresholds typed twice, checked by code
Built: Two copies of the Q3B limits table (entry_a typed by me, entry_b typed by Hil). Code compares them and refuses on any difference.
Each row must also appear word for word on page 11 of the PDF. Then the rows go into a database table that can only grow.
Why this way: One typo changes a regulatory decision. Alternative NOT chosen: one person types it and code trusts it, because nobody would catch a slip.
Also not chosen: update rows in place; a new guideline version adds rows so old answers stay reproducible.
New words: double entry = two people type the same data; append-only = rows can be added, never changed or deleted; boundary = the exact edge of a range (is 1 g in or out?).
Look at: ectd_engine/rules/q3b.py - compare() lists the exact differences; _inside() holds the edge rules.
Try it: python -c "from ectd_engine.rules import q3b; print(q3b.threshold('identification','10'))" - prints 0.5, 20 and a rule id.
Remember: Two matching copies and one PDF quote are three witnesses; one witness alone is not enough.
