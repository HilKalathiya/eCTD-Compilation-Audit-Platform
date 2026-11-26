# Checkpoint A - one-command demo (T-075, rebuilt on the real CSV in T-076)

Plan v2 (`handoff/brain/04_plan_and_next_steps.md`, line 62): **"CSV -> facts -> stats -> Gemma draft -> validator -> rendered doc; planted wrong number rejected; classmate plants 10 errors. 2-minute video."**

## The plan, line item by line item
| # | Plan item | Status | Where |
|---|-----------|--------|-------|
| 1 | CSV -> facts | **DONE** | demo step 1: `data/stability/finerenone_stability.csv` (66 data lines) -> 70 facts in memory (no database); each keeps its CSV line and FDA review page |
| 2 | facts -> stats | **DONE** | demo step 2: ICH Q1E estimate, range and outside-limit counts, computed by code from the same rows; inputs are printed |
| 3 | Gemma draft | **DONE** (with retries) | demo step 3: real `gemma4:e4b` run `evidence/T-076/demo/run2` (one earlier run, `run1`, FAILED, see limits) |
| 4 | validator (gates a-i + cross-check) | **DONE** | demo step 4 + the source trace |
| 5 | rendered document | **DONE** | HTML and Word file, saved and re-read by the cross-check |
| 6 | planted wrong number rejected | **DONE** | demo step 5 (number changed in a copy) and step 6 (digit typed by the model) |
| 7 | classmate plants 10 errors | **NOT YET** | kit is READY (`tools/classmate_kit.py`, `docs/CLASSMATE_TEST.md`, kit `evidence/T-076/classmate/kit1`); it needs a person who is not on the team. A scripted rehearsal exists; it is not this test |
| 8 | 2-minute video | **NOT YET** | script is ready (below); Hil records it |

## How to run it
```
python tools/demo_checkpoint_a.py --out evidence/T-077/run1 --log evidence/T-077/run1_console.txt    # real Gemma (Ollama running, gemma4:e4b pulled; needs Available memory >= 3000 MB)
python tools/demo_checkpoint_a.py --out <new folder> --mock --csv <copy of the CSV>                    # same chain on another copy of the CSV (same columns)
python tools/demo_checkpoint_a.py --check-docx <edited.docx> --kit evidence/T-076/classmate/kit1       # check ONE Word file: prints the numbers it rejects
python tools/demo_checkpoint_a.py --out <new folder> --mock                                                      # scripted model, no Gemma needed
python tools/demo_checkpoint_a.py --out <new folder> --mock --synthetic                                          # the old INVENTED test task, labelled SYNTHETIC
```
`--out` must be a new folder every time (an existing one is refused, exit 2). `--log` saves the console text (the script writes the file itself). No database is needed.
Exit code 0 only if steps 1-4 pass (including the source trace) AND both planted errors are rejected. If a plant is accepted the demo prints "NOT REJECTED (BAD)" and exits 1.

## What each step proves (default mode = the CSV chain)
1. **Facts** - prints one PUBLIC fact (the proposed shelf life, with its CSV line text and FDA review page 3) and one DEMO fact (an Assay result, with the label the writer must show and "(b)(4) redacted in FDA review page 7").
2. **Stats** - Q1E on the 8 Assay rows at 25C/60%RH (inputs printed with their CSV lines), plus range and outside-limit counts from the same rows.
3. **Draft** - Gemma writes sentences with `[[slots]]` only; the raw draft of one section is printed and has no digit.
4. **Gates + cross-check + source trace** - wording gates (a-i), then an independent check of the saved HTML and Word files. The source trace then follows every number in both files to its fact id and to a line of the CSV, which it re-reads from the file with its own reader. It prints the count and requires it to equal the cross-check total (run2: 66 numbers = 33 in HTML + 33 in Word; 66 traced, 0 not; cross-check total 66).
5. **Plant 1** - one number in a COPY of the document is changed (shelf life 36 -> 48). The cross-check rejects it, naming the number (no fact owns 48) and the fact that owned the place.
6. **Plant 2** - a draft where the model typed a number itself. Gate (a) rejects it.
7. **Run fingerprint** - sha256 of the HTML, Word, the attempts log, the graph snapshot and the CSV, plus a short fingerprint made from them. It lets one run be found again. It is **not a ledger** and does not protect any file from being edited.

## Honest limits
- **Every number in the saved files has a source row in the CSV**: this is checked by the source trace in the default mode, and only there. `--synthetic` mode uses invented numbers and prints "SYNTHETIC MODE"; the trace does not run in it.
- **26 of the 33 numbers in each file (HTML and Word) come from invented DEMO rows.** Only 7 are public (shelf life 36, storage 20 and 25, excursion 15 and 30, study durations 36 and 6; FDA review pages 3 and 5). The 24 Assay, Degradation product and Dissolution numbers and the 2 specification limits are invented (labelled DEMO, source "redacted (b)(4)").
- Two specification limits (Dissolution NLT 80, Degradation product NMT 0.50) are read from the **limit column** of the CSV rows (their line is the source). What really happens: the Lek specification row is loaded **as a template** (it only gives the field layout); **every value is overwritten from the CSV** (value, kind NLT/NMT, unit, source file, line, page, label). Both spec ids keep the name `M23-SPEC-LEK-...` only because the cross-check reads spec facts by that prefix; the trace follows `doc_id` and `locator`, which say the CSV. The unit is the CSV's own unit cell ("% dissolved", "% area"), not typed in the code (a test changes the limit in a copy of the CSV and shows 75 in both files). Assay has a two-sided range (95.0-105.0) that the specification sentence patterns cannot hold, so Assay gets the range sentence only (no within/outside claim).
- **DEMO label, what is done and what is not.** The sentence "Stability was demonstrated for ..." (and the other study wordings) depends on DEMO results, so the demo puts "In illustrative demonstration data," in front of it, in both HTML and Word (after the gates, before saving; no number changes). The **specification table rows are NOT labelled row by row**: the frozen cross-check accepts a row only in the exact form `test, kind number unit`, and a test shows it rejects a row with the label inside. The table sits directly under the labelled sentence "In illustrative demonstration data, the drug product specification below lists ...". Labelling each row needs a change to the cross-check (an engine card).
- The trace follows `doc_id` and `locator`, never the id name, so the `M23-SPEC-LEK-` name does not hide a non-CSV source (a test gives a fact another source and the demo exits 1).
- The 2.3 writer is a **template filler**: Gemma chooses one allowed sentence pattern per place and the slot names; code writes every value. It is not free writing.
- **The test data are DEMO**: only the shelf life, storage, excursion and study-duration rows are public (FDA review pages 3 and 5); every Assay, Degradation product and Dissolution number is invented and labelled in the document by "In illustrative demonstration data,".
- The Q1E estimate in step 2 is 48.00 months and equals its cap (the Assay barely drifts: 100.00 to 99.28 over 36 months). The proposed shelf life in the document is 36 months, its own fact. The demo does not claim the two agree.
- **Gemma needs retries.** `run1` FAILED at step 4: the model wrote the same intro sentence ("... specification below lists these tests and their acceptance criteria") in all 4 allowed drafts, the closed pattern list rejected it each time, and the run stopped (23 drafts, 13 rejections, exit 1). That run is kept. `run1` used a one-row specification table; the table was then given a second row (Degradation product) and `run2` passed with 21 drafts for 11 sections (10 rejections, then corrected). No prompt or gate was changed between them. The change of the table is not proven to be the cause (the four rejected drafts in run1 were word for word identical, because the temperature is 0, so the retry feedback did not move the model; run2 is one run, not a statistic). Expect that a real run can fail.
- **The real Gemma run `evidence/T-076/demo/run2` was made before the T-077 fixes** (Dissolution unit typed as "%", no label on the study sentence). T-077 tried a new real run but free memory was 2593 MB (under the 3000 MB rule), so none was made (`evidence/T-077/real_gemma_run_not_done.txt`). The T-077 code is proven only with the scripted model (`evidence/T-077/mock3`).
- Only these 66 CSV lines were run through the chain; nothing here tests other data.
- Not covered here: the classmate test (needs a person), the ledger (Phase 4, not built), the review UI.

## What to say (2-minute video script)
- (0:00) "I will show that a language model can help write a regulatory document without ever writing a number."
- (0:15) Step 1: "Every number is a fact with its source line. Here is one public row and one labelled demo row from the CSV."
- (0:35) Step 2: "Code, not the model, computes the shelf-life estimate, from those same rows."
- (0:50) Step 3: "Gemma only writes sentences with empty slots. Look: no digits in what it wrote."
- (1:05) Step 4: "Code fills the numbers. An independent checker matches every number in the Word and HTML file to its fact, and a trace follows each one back to a line of the CSV."
- (1:20) Step 5: "Now I cheat: I change one number in a copy. The checker rejects it and tells me which number and which fact."
- (1:40) Step 6: "And if the model types a number itself, the gate rejects the draft."
- (1:50) "At the end a run fingerprint lets anyone find this exact run again. Limits: demo data, template filler, retries happen, and the classmate test is still to do."
