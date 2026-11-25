# Checkpoint A - one-command demo

Plan v2 (`handoff/brain/04_plan_and_next_steps.md`, line 62): **"CSV -> facts -> stats -> Gemma draft -> validator -> rendered doc; planted wrong number rejected; classmate plants 10 errors. 2-minute video."**
This demo covers everything in that line except the classmate part (people from outside plant 10 errors: still to do).

## How to run it
```
python tools/demo_checkpoint_a.py --out evidence/T-075/demo/run2 --log evidence/T-075/demo/run2_console.txt     # real Gemma (Ollama running, gemma4:e4b pulled)
python tools/demo_checkpoint_a.py --out <new folder> --mock                                                       # scripted model, no Gemma needed
```
`--out` must be a new folder every time (an existing one is refused, exit 2). `--log` saves the console text (the script writes the file itself). No database is needed.
Exit code 0 only if steps 1-4 pass AND both planted errors are rejected. If a plant is accepted the demo prints "NOT REJECTED (BAD)" and exits 1.

## What each step proves
1. **Facts** - a number only exists as a fact with a source. Shown: one fact from the public Lek `Laboratory.csv` (source row) and one fact from the DEMO task (labelled SYNTHETIC; invented numbers).
2. **Stats** - code computes a shelf-life estimate (ICH Q1E, Decimal) and a range from the facts. The model never computes.
3. **Draft** - Gemma writes sentences with `[[slots]]` only. The raw draft is printed; it has no digit.
4. **Gates + cross-check** - the wording gates (a-i) accept the draft; code fills the values; an independent cross-check reads the saved HTML and Word files and matches every number to its fact. Paths are printed.
5. **Plant 1** - one number in a COPY of the document is changed (shelf life 12 -> 24). The cross-check rejects it and names the number (24, no fact owns it) and the fact that owned the place.
6. **Plant 2** - a draft where the model typed a number itself. Gate (a) rejects it.
7. **Trace** - sha256 of the HTML, Word, the attempts log and the graph snapshot, plus a short RUN ID. (The Word file holds a time stamp, so the RUN ID differs between runs; it identifies THIS run.)

## Honest limits
- The 2.3 writer is a **template filler**: Gemma chooses one allowed sentence pattern per place and the slot names; code writes every value. It is not free writing.
- The tested data are **DEMO / SYNTHETIC** (invented numbers, labelled in the document by "In illustrative demonstration data,"). The only real public specification fact is **Dissolution** in Kerendia; Assay and Degradation product have none, so on real Kerendia they get the range sentence only.
- The Q1E estimate printed in step 2 (10.16 months) is a worked example; the proposed shelf life in the document (12 months) is its own fact. They are not the same number and the demo does not claim they agree.
- Retries happen: in run1 Gemma needed 11 drafts for 6 sections (5 rejected by the gates, then corrected). That is the gates working, not a failure.
- Not covered here: the classmate-plants-10-errors test, the ledger (Phase 4), the review UI.

## What to say (2-minute video script)
- (0:00) "I will show that a language model can help write a regulatory document without ever writing a number."
- (0:15) Step 1: "Every number is a fact with its source row. Here is one from a public CSV, and one from labelled demo data."
- (0:35) Step 2: "Code, not the model, computes the shelf-life estimate."
- (0:50) Step 3: "Gemma only writes sentences with empty slots. Look: no digits in what it wrote."
- (1:05) Step 4: "Code fills the numbers, then an independent checker matches every number in the Word and HTML file to its fact."
- (1:20) Step 5: "Now I cheat: I change one number in a copy. The checker rejects it and tells me which number and which fact."
- (1:40) Step 6: "And if the model types a number itself, the gate rejects the draft."
- (1:50) "At the end a run ID lets anyone find this exact run again. Limits: demo data, template filler, one real public spec."
