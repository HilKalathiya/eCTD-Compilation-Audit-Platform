# LEARN T-033 - a quote counts only if it is in the real PDF
Built: cite.py opens the original PDF, checks its fingerprint, and accepts a quote only if the exact words are on that page.
Tests plant a changed word, a changed digit, a wrong page, a changed PDF and an empty quote: all are refused.
Why this way: We did NOT compare against our saved chunks, because they were cut and cleaned by our own code and could hide a mistake. The PDF is the truth.
We did NOT loosen the matching: 26 of 30 test quotes pass, and the 4 that fail show real flaws in our chunk text.
New words: verbatim = word for word; sha256 = a fingerprint of a file; normalise = tidy spaces and quotes before comparing
Look at: ectd_engine/knowledge/cite.py - normalise() makes only four small changes.
Try it: python -m unittest tests.test_citations.VerifyTests - 14 tests pass, the planted ones prove it can say no.
Remember: A quote is only a quote if a reviewer can find the exact words on that page.
