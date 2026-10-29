# LEARN T-010 - The database double-checks every fact
Built: Rules inside the facts table (not blank, not NaN, month >= 0, allowed lineage, plain number text, locator shape).
A test also compares schema.py's checks with the table's rules so they cannot drift apart.
Why this way: We did NOT rely on Python alone, because then a bug or a skipped Python step lets bad data in.
Two separate checks mean each one can fail on its own and the other still catches it.
New words: CHECK constraint = a rule stored in the table; defence in depth = several independent checks.
Look at: ectd_engine/db/migrations/002_gate_checks.sql - one line per rule, named facts_<thing>.
Try it: python -m unittest discover tests_live -v - lines starting REFUSED show the database saying no.
Remember: Trust, but make the database verify.
