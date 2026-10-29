# LEARN T-016 - Reading numbers out of an FDA PDF, with their exact spot
Built: A loader that opens the Kerendia chemistry review PDF, finds 8 listed numbers, and records the page and a box around each word.
Each number goes through the gate like every other fact.
Why this way: We read the PDF's own text layer (exact words and positions), not OCR (a program guessing letters from a picture). OCR is for scanned pages later (C1.7b).
A number is only accepted if its page line also holds the label words, so a mistyped "63" or a wrong page fails loudly.
New words: word box = the rectangle (x0,y0,x1,y1) around one word on a page; text layer = real text inside a PDF, not a picture; locator = the "page=3;box=..." address of a fact.
Look at: ectd_engine/loaders/kerendia_targets.json - each target says page, expected text, and label words.
Try it: python -m ectd_engine.loaders.fda_pdf --dry-run - 8 lines, each with page + box (quarantined until ranges are added).
Remember: A number without a page and a box cannot be checked in one click.
