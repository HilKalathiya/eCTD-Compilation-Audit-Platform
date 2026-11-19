# LEARN T-051 - Prose rules become a gate
Built: The grammar rules now live in one file, and the writing loop rejects any draft whose finished text breaks one.
Why this way: One shared list instead of a copy in the tests and another in the loop, so they can never drift apart. We did NOT leave the rules only in tests, because tests do not stop a bad live paragraph.
New words: gate = a check that blocks bad output before it is accepted
Look at: ectd_engine/writer/spec_prose.py - PROSE_RULES, one named rule per line
Try it: python evidence/T-051/rerender.py - you should see "0 rejects" out of 150
Remember: A rule only counts when it runs on live output, not just in tests.
