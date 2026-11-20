# LEARN T-054 - No number can hide from the trace check
Built: A second check that looks at every digit in the text and the HTML, not only the numbers the finder knows. The finder also learned ordinals (first..twentieth), halves/quarters, ".5" and "1,000".
Why this way: The second check does not use the number finder, so if the finder misses a shape, the digit check still sees it. We did NOT just widen the finder alone, because one list can always miss something.
Batch counts are now digits ("12 batches"), the same as P.5.6. Batch writer tests that expected words, changed to digits:
- tests/test_batch_writer.py test_counts_extremes_ties_and_mean: "four batches" -> "4 batches"
- test_excluded_batches_become_facts: "two batches" -> "2 batches" (twice, n_excluded and n_batches)
- test_opening_sentence_is_code_text: "one batch" -> "1 batch"
- test_rendered_text_re_read: replace "three batches" -> "3 batches", "four batches" -> "4 batches"
New words: uncovered digit = a digit in the final text that sits in no number span and no exempt span; ordinal = first, second, third...
Look at: ectd_engine/render/numbers.py - uncovered_digits has no number regex in it.
Try it: python tools/render_doc.py --out evidence/T-054/ - the report shows "uncovered 0".
Remember: Check from two directions, so one blind spot is not enough to hide a number.
