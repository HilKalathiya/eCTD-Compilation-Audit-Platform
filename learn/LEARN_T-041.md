# LEARN T-041 - A second section: batch results table + one checked paragraph
Built: for each Lek test, code writes the results table and every number (how many batches, lowest, highest, mean); the model only writes one paragraph of words with [[placeholders]].
Why this way: batch results have no specification limits, so any "meets the limit" wording is wrong; the checker has its own bad-word list. Not chosen: reusing the stability checker as it is, because it expects trends and limits that do not exist here.
New words: planted error = a mistake we add on purpose to see if the checker notices; quarantined = a value the gate refused to store; mean = the average.
Look at: ectd_engine/validator/batch.py - `exclusion_problems`: exclusion must be mentioned if, and only if, batches were excluded.
Try it: python -m unittest tests.test_mutation_batch - it should print OK (7884 planted errors, all caught).
Remember: a check only counts if a planted mistake can make it fail, and the planted mistake must be caught by the rule meant for it.
