# LEARN T-059 - Flag every sentence we do not recognise
Built: A list of the exact sentence forms the writer makes (shapes). A sentence is trusted only if it fits a shape and its numbers equal the placed facts; anything else is flagged.
Why this way: We did NOT keep hunting for bad words (a blocklist), because a new wording slips past it. A list of allowed forms flips it: new wording is flagged by default.
New words: shape = an allowed sentence form with blanks for numbers; allow-list = only listed things pass
Look at: ectd_engine/review/shapes.py - SENTENCE_SHAPES, each with the fact its numbers must equal
Try it: python tools/reread_export.py evidence/T-056/ --out evidence/T-059/ - 3589 numbers == placements, 0 flags
Remember: Trust what you recognise; flag the rest.
