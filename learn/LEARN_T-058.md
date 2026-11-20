# LEARN T-058 - Make the claim check harder to dodge
Built: More claim words (passed, OOS, robust...), quotes are now checked unless they are a stored source quote, and "range from X to Y" is checked against the real lowest and highest results.
Why this way: We did NOT skip all quoted text, because anyone can put a claim inside quotes. We did NOT let "passed" count as backed by a fact, so it always goes to a human.
New words: overclaim = a sentence that says more than the facts show; exact match = same text, character for character
Look at: tests/test_entail.py - OVERCLAIMS (20 bad sentences) and TRUE_SENTENCES (5 good ones)
Try it: python -m unittest tests.test_entail - all OK; 20 of 20 bad sentences flagged
Remember: A check you can talk your way around is not a check.
