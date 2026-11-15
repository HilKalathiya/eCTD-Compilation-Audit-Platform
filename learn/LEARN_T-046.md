# LEARN T-046 - Writing the "why this limit" paragraph without letting the model overclaim
Built: For each spec limit the model writes one paragraph with [[placeholders]]; code fills in the limit, its direction, the basis, the assumed dose and the Q3B quote.
A new checker rejects wording that makes a declared limit look sourced, hides the assumed dose, or claims safety.
Why this way: The rules follow each limit's basis (declared vs Q3B), not one big word list; a declared limit may never sound sourced.
We did NOT reuse the batch/stability word lists: they reject correct words like "daily" in "maximum daily dose".
New words: basis = what a limit rests on (a source, or just declared) | assumption = a value we chose, not one a source gave | planted error = a mistake we add on purpose to see if the checker notices
Look at: ectd_engine/validator/spec.py - SOURCE_WORDS (declared) and basis_problems (q3b needs "assumed" next to [[mdd]]).
Try it: python tools/writer_run.py --kind p56 --backend mock --out %TEMP%\t046 - "5/5 accepted".
Remember: The model may describe a limit, but only code may say where it came from.
