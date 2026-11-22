# LEARN T-060 - Headings and table cells must match the plan exactly
Built: The re-read tool now knows what every heading and table row should be, from the plan and task files on disk. Anything different is flagged as heading:<text> or row:<batch id>.
Why this way: We did NOT just scan headings for bad words. A heading can say anything harmless-looking, so we compare it to the exact expected text at its position instead.
New words: exact match = same text character for character; position = the place in the document order
Look at: ectd_engine/review/layout.py - check_headings and check_row
Try it: python tools/reread_export.py evidence/T-056/ --out evidence/T-060/ - 0 flags and 3589 == 3589
Remember: If the code did not put it there, it must not be there.
