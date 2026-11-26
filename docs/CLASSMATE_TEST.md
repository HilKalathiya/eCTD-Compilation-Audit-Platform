# Classmate test - a person who is not on the team tries to fool the checker

Why: tests made by the team only test what the team thought of. A person who did not build the system will try things we did not.
**Status: kit READY, test NOT YET DONE.** It needs a real person. The scripted "classmate" in `tests/test_classmate_kit.py` is a rehearsal of the kit, not this test.

## For the organiser (Hil)
1. Make a kit from a finished demo run that PASSED. The ready kit `evidence/T-076/classmate/kit1` was made from `evidence/T-076/demo/run2` (the run that passed; `run1` FAILED and has no usable document). To make another one:
   ```
   python tools/classmate_kit.py prepare --out evidence/T-077/classmate/kit1 --run evidence/T-076/demo/run2
   ```
   Without `--run` the kit makes its own scripted-mock demo run first. The kit folder must be new (an existing one is refused).
2. Give the person **only** the folder `kit1/for_classmate/` (HTML, Word, CSV and `INSTRUCTIONS.txt`). Do **not** give them `trusted/` (the untouched copies and facts).
3. They change up to 10 numbers or claims anywhere (document or CSV) and list every change in `kit1/answers.csv` (columns: `n, file, csv_line, near, original_text, new_text, kind`).
4. When they hand it back, score it:
   ```
   python tools/classmate_kit.py score --dir evidence/T-076/classmate/kit1
   ```
   Score writes `score_<time>.json` into the kit folder (never overwrites) and prints one line per change.

## Quick check of ONE edited Word file
One plain command: it runs the number cross-check on that file only and prints every number it rejects (exit code 1 if any, 0 if none):
```
python tools/demo_checkpoint_a.py --check-docx <their edited M23.docx> --kit evidence/T-076/classmate/kit1
```
Example of what it prints when one number was changed: `REJECTED number 101.00 next to fact ...` and the fact `M23-STAT|25C/60%RH|Assay|max` that lost its number. It checks numbers, units and their places only. A changed sentence or a changed CSV needs the full `score` step above.

## How scoring works (two separate steps)
- **Step 1 `run_checks`** looks only at the edited files and the trusted copies. It never opens `answers.csv` (a test proves this, and a second test deletes the file and runs step 1 anyway).
  Checks that run:
  - fingerprint of each file against the one handed out (says THAT a file changed, never WHERE);
  - CSV data rules (`check_rows`: bad source, DEMO label removed or added, value outside its limit, unreadable value);
  - the saved trusted document cross-checked against facts rebuilt from the edited CSV (lines the rules already flagged are left out, so one bad line does not hide the others);
  - the edited HTML and Word file cross-checked against the trusted facts (every number, its unit, its place);
  - `m23_compare4` on the edited HTML (claims, DEMO label, links);
  - a wording check on both files: every sentence must fit one allowed pattern, the expected sentences must all be there in order, and a claim must agree with the data.
- **Step 2 `match_answers`** then reads `answers.csv` and gives each change one result:
  - **CAUGHT**: a content check named the place (the result lists which check);
  - **NOT LOCATED**: the file is flagged only because its fingerprint changed; no content check found the change. This is counted as **not caught** in the totals;
  - **MISSED**: nothing flagged it, not even the fingerprint.
  Findings that no listed change explains are printed too (they can be side effects of one change, or a change the person forgot to list).

## Known limits (said before the real test, so a miss is no surprise)
- A change in the CSV that stays inside its limits and is never printed in the document (for example a middle Assay value) can only be seen by the fingerprint. It is reported as NOT LOCATED. The scripted rehearsal contains one of these on purpose.
- Matching a change to a finding uses the words the person wrote in `near`, `original_text`, `new_text`. A vague description can make a real catch look like "not located". The score file keeps every finding so a person can check.
- Changes that keep every number, unit and sentence pattern valid (for example swapping two allowed wordings) are not changes the checks can see; the wording check allows every wording in the closed pattern list.
- `kit1` holds the T-076 run2 document, made before the T-077 fixes (spec unit "%", no label on the study sentence). It is self-consistent, so scoring works; a kit made from a new run holds the T-077 wording.
- The scripted rehearsal (10 edits made by code) found 9 caught and 1 not located (the middle CSV value). It is NOT the classmate test.
