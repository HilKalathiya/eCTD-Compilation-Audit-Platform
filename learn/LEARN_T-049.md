# LEARN T-049 - Make the paragraphs read like real English
Built: Code now writes "17 of 25 results" and "which is declared by the author...", and quotes only the one table row for the dose.
Why this way: We fix the words in the code that fills the values, not by asking the model again. We did NOT loosen the checker, because the facts were already right; only the wording was bad.
New words: regression test = a test that keeps an old mistake from coming back; bare number = a number with no noun after it
Look at: ectd_engine/writer/spec_facts.py - render_paragraph and q3b_row_quote
Try it: python -m unittest tests.test_spec_writer -k hil - you should see 4 dots and OK
Remember: A finding from a human reviewer should become a test the same day.
