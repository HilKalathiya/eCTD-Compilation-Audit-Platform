# LEARN T-066 - Scoring the blind sheet honestly, and a sheet you cannot fill in wrong
Built: A scorer that counts how many planted mistakes were spotted and how many good paragraphs were accepted.
Also a new sheet where the answer column sits right next to the row number.
Why this way: The scorer refuses an empty answer column instead of guessing, so a wrong-column mistake cannot give a fake score.
We did NOT edit the old T-065 sheet to move the answers; that would change the evidence.
New words: verdict = your right/wrong answer for one row; refuse = stop with a message instead of guessing.
Look at: evidence/T-065/score.md - it says 2/3 caught, one miss (R15), not a perfect score.
Try it: python tools/score_blind.py --sheet evidence/T-065/blind.csv --key evidence/T-065/blind_key.csv - it says REFUSED (empty column).
Remember: A check that can say "no, I cannot score this" is more honest than one that always gives a number.
