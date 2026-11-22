# LEARN T-067 - A clean blind sheet, with the answers kept in one place
Built: A new test set the model had never seen, 25 paragraphs written by Gemma, and a sheet where 3 are secretly wrong.
The answers live only in the key file.
Why this way: We use only model-written paragraphs, so Hil judges the real writer, not code. We did NOT mix in code-written ones (as in T-066) because that tests the wrong thing.
Also, notes and reports must never say which rows are wrong, or the "blind" part is lost.
New words: leak = the answer shown somewhere the judge can see it; withdrawn = taken back because it is no longer trustworthy.
Look at: evidence/T-067/blind.csv - the verdict column is right after the row number, and nothing hints at the wrong ones.
Try it: python tools/score_blind.py --sheet evidence/T-067/blind.csv --key evidence/T-067/blind_key.csv - it says REFUSED until Hil fills it in.
Remember: A blind test only works if the answers stay hidden everywhere.
