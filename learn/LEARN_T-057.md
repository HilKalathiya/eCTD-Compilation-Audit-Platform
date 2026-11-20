# LEARN T-057 - Catch claims the facts do not back up
Built: A checker that reads each sentence and flags claims like "complies" or "no new signals" when no fact supports them. A second tool re-opens the Word file with a different reader and checks it again.
Why this way: Flags go to a human reviewer instead of rejecting the text, because a flag can be a false alarm. We did NOT reuse python-docx for the re-read, since the same library could repeat the same mistake; a zip + XML reader is a separate path.
New words: entailment = "is this sentence backed by a fact?"; claim word = a word that asserts something (complies, within, stable)
Look at: ectd_engine/review/entail.py - RULES ties each claim to a fact (n_outside == 0)
Try it: python tools/reread_export.py evidence/T-056/ --out evidence/T-057/ - numbers 3589 == placements 3589 and 4 flags
Remember: A claim with no fact behind it gets flagged, never passed.
