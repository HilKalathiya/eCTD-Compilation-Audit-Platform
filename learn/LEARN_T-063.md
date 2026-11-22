# LEARN T-063 - Checks for the stability paragraph
Built: A checker that reads each sentence of a stability paragraph and compares its numbers with the facts.
A no-model "mock writer" drafts a paragraph from the facts so we can test the checker.
Why this way: We allow only a short list of sentence forms (an allowlist) instead of trying to spot bad sentences, because unknown sentences are the risky ones.
We did NOT let the checker accept "no significant change" on its own; it needs a fact first.
New words: allowlist = list of the only things permitted; mutation test = plant one error on purpose to see the check catch it; verbatim = word for word.
Look at: ectd_engine/validator/stability.py - each shape lists which fact each number must equal.
Try it: python -m unittest tests.test_stability_validator - you should see 15 tests, OK.
Remember: Sentences made of made-up data must always say "illustrative demonstration data".
