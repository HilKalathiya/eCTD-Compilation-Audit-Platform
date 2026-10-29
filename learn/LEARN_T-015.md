# LEARN T-015 - Reading the Lek lab sheet into facts
Built: A loader that turns every number in Laboratory.csv into a sourced fact and sends it through the gate.
Rows where a part impurity is bigger than the total are held back (quarantined) instead of stored.
Why this way: The gate only sees one number at a time, so "part > total" is checked in the loader, where the whole row is visible.
We did NOT drop bad rows silently: each held-back fact is written to quarantine with a reason.
New words: cross-field check = a rule comparing two numbers in the same row; dry run = count what would happen, store nothing.
Look at: ectd_engine/loaders/lek.py - _part_exceeds_total and the three-fact quarantine.
Try it: python -m ectd_engine.loaders.lek --dry-run - "accepted 4965, quarantined 60 (20 batches)".
Remember: A number that contradicts its own row is not a fact yet.
