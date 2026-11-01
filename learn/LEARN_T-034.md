# LEARN T-034 - Real quotes with ≤ ± now pass; page headers are dropped
Built: One shared list turns the PDF's hidden font codes into real signs (≤ ± bullet). The chunker and the quote checker both use it.
Running page titles and page numbers are cut out of the chunks. The watcher has two fewer false alarms.
Why this way: One shared list, so chunks and checker can never disagree. We did NOT add more clean-ups (like treating < as ≤): that would let wrong quotes pass.
New words: private-use code = a font's hidden character number with no normal meaning; running header = title repeated at the top of many pages.
Look at: ectd_engine/knowledge/chunk.py - SYMBOL_MAP (only 3 codes, the ones found in the 5 PDFs).
Try it: python -m unittest tests.test_citations.VerifyTests - OK, including a test where "<" instead of "≤" is refused.
Remember: Fix the data once, in one place, and test the checker both ways.
