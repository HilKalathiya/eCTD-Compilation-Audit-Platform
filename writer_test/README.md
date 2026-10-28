# Writer test: can a free local model draft eCTD stability text?

This tests the $0 writer pipeline on 8 synthetic stability sections (3.2.P.8.3).
Code computes every number and judgement; the model writes only a 2-4 sentence
discussion using `[[placeholders]]`; a validator rejects bad drafts; code fills
in the values. The data is made up, so nothing confidential goes anywhere.

It answers three questions with numbers:
1. How often does the model pass the validator on the first draft?
2. How many minutes does one section take on your laptop?
3. How do its paragraphs compare with Claude's, rated blind?

No Python packages to install: it uses only the standard library.

## Run it on your laptop (Windows, 16 GB RAM)

1. Install Ollama for Windows from https://ollama.com/download and open it once.
2. In a terminal, download the model (several GB, one time):
   ```
   ollama pull gemma4:e4b
   ```
3. Install Python 3.10 or newer from https://www.python.org/downloads/ (tick "Add to PATH").
4. Close Chrome and other heavy apps, then in a terminal:
   ```
   cd E:\E\Project\writer_test
   python -m unittest discover tests
   python -m writer_test.run --model gemma4:e4b --export-prompts
   ```
5. Read `outputs\ollama_gemma4-e4b\summary.md`. The finished sections are in `sections\`.

The first draft also loads the model, so it is slower than the rest.

## What counts as "it works"

- At least 7 of 8 sections pass within 4 drafts, and
- the mean time is under about 3 minutes per section on your laptop, and
- the finished paragraphs read correctly with the values filled in. The run
  prints each one; the validator catches common breaks but not every grammar slip.

- every accepted paragraph is also re-read from the finished text against the raw table
  (`rendercheck.py`), so a value, batch or month that does not match the data is rejected.

If it fails, `summary.md` lists why drafts failed. Then try, in order: a bigger
model on Kaggle (below), more drafts (`--max-drafts 6`), or fine-tuning.

## Run the bigger model free on Kaggle

Kaggle gives about 30 free GPU hours a week. New notebook, then Settings:
Accelerator = GPU T4 x2, Internet = on. Upload this folder as a Kaggle
Dataset (zip it first), add it to the notebook, then run these cells:

Cell 1, install (Ollama's installer needs zstd, which Kaggle does not have):
```
!apt-get update -qq && apt-get install -y -qq zstd
!curl -fsSL https://ollama.com/install.sh | sh
```

Cell 2, start the server and wait until it answers:
```
import subprocess, time, urllib.request
server = subprocess.Popen(["ollama", "serve"], stdout=open("/kaggle/working/ollama.log", "w"),
                          stderr=subprocess.STDOUT)
for _ in range(60):
    try:
        urllib.request.urlopen("http://127.0.0.1:11434"); print("Ollama is running"); break
    except Exception:
        time.sleep(1)
```

Cell 3, download the model and run the test:
```
!ollama pull gemma4:26b
!cp -r /kaggle/input/YOUR-DATASET-NAME/writer_test /kaggle/working/
%cd /kaggle/working/writer_test
!python -m writer_test.run --model gemma4:26b --export-prompts
!ollama ps
```
`ollama ps` should show the model on the GPU. If it says CPU, check that the
accelerator is set to GPU.

If `gemma4:26b` does not fit in GPU memory, run `gemma4:e4b` there instead; it
will still be much faster than your laptop.

Kaggle reads the folder you uploaded, not the one on your laptop. After any change here,
zip the folder again and upload it as a NEW VERSION of the same Kaggle Dataset, or the notebook
will keep running the old code.

If every draft fails with "empty output" or "got 0 sentences", the model spent
its whole token budget thinking. Thinking is off by default (`--think off`);
if your Ollama version ignores that, add `--num-predict 2000`.

## Compare with Claude, blind

You already pay for the Claude app, so this costs nothing extra.

1. Each file in `outputs\ollama_gemma4-e4b\prompts\` is one full prompt.
   Paste it into the Claude app and copy back only the paragraph it writes.
2. Save each paragraph as `reference\<task_id>.txt`, for example
   `reference\lt_total_impurities.txt`. Doing 4 or 5 tasks is enough.
3. Run:
   ```
   python -m writer_test.compare --run outputs\ollama_gemma4-e4b
   ```
   You see both paragraphs as A and B in random order, rate each 1-5, and the
   names are revealed at the end. The validator also checks Claude's paragraphs.

## Useful options

| Option | Meaning |
| --- | --- |
| `--max-drafts 4` | most drafts per section before giving up |
| `--tasks lt_assay,lt_water` | run only some sections |
| `--think off` | turn off hidden reasoning (default); `on` is slower |
| `--num-predict 600` | most tokens per draft |
| `--backend openai --base-url http://localhost:8080/v1` | use llama.cpp's llama-server or vLLM instead of Ollama |
| `--audit 20` | 20 drafts per section, none discarded, written to audit.csv for hand labelling |
| `--backend mock` | fake model, to check the code without downloading anything |

## Wrong binding: the value is right but sits in the wrong sentence

A value-only check passes "the highest result was [[min_value]]". The design here removes the
model's chance to bind wrongly, then checks what is left:

1. Compound facts. A result fact carries its own batch and month: `0.30% (Batch B3, Month 24)`.
   There is no separate batch or month fact, so the model cannot pair a value with the wrong batch.
2. Closed vocabulary. Words that name a role (highest, lowest, initial, last), a test, a condition,
   a batch ("second batch"), a time ("early", "after a year"), a cause or a comparison between two
   results are allowed only next to a placeholder that has that role, or not at all. A sentence may
   start only with a plain connecting word or the tested attribute, which catches a test name the
   registry does not know (only when it starts a sentence).
3. Code decides the claims. Trend, compliance and the must-mention fact are computed; the draft is
   rejected if its words contradict them.
4. Independent re-read of the finished text (`rendercheck.py`) against the raw table.

### Test the checks with planted errors

```
python -m writer_test.mutation_test --tasks 1000 --per-type 300
```
It builds correct paragraphs, plants one error of each of 26 kinds (plus 4 tampering kinds on the
finished text), and reports how many were caught, how many correct paragraphs were wrongly
rejected, and 10 correct paraphrases. Add `--seed 2` to repeat with new data. Pass mark: every
planted error caught and no correct paragraph rejected. The report also prints the 95% upper bound
on the miss rate (zero misses in 300 tries still leaves up to 1.0%).

Limit: the author of the checks planted these errors, so this test is friendly. The honest test
is the model's own mistakes:

### Audit the model's own mistakes

```
python -m writer_test.run --model gemma4:e4b --audit 20
```
Close Excel first. Each run writes a new file, so nothing is overwritten.
Writes `outputs\ollama_gemma4-e4b\audit_<date_time>.csv` (and a `.jsonl` copy saved draft by draft): 20 drafts for each of the 8 sections, none thrown
away (160 drafts, about 30 minutes). Open it in Excel and filter `accepted` to yes. For each row,
read `finished_text` beside the `data (to check against)` column (spec, months, and each batch's
results) and write ok, wrong or awkward in the `human_verdict` column. Wrong means a fact,
batch, month, trend or pass/fail is not what the data says. Pass mark: at least 100
accepted paragraphs and not one "wrong". One "wrong" means a check is missing: add it, then rerun.
`raw_draft` keeps the model's own text with the placeholders, so any new check can be tested on old drafts.

You do not need to be a stability expert to label: every judgement is a lookup. Does each batch, month and
value match the table? Is "highest" the biggest number and "lowest" the smallest? Does "initial" mean
Month 0 and "last" the final month? Does the trend match first versus last? Is the pass/fail right?
Use three labels: `ok`; `awkward` (clumsy, every fact right); `misleading` (each number is true but the
sentence implies something false); `wrong` (false as written).

First audit (Gemma 4 e4b, 28 Oct): 102 accepted of 160. Read by hand: 61 ok, 30 awkward, 7 misleading,
4 wrong. That failed the pass mark, and seven new checks were added (single result called a range,
change between two batches' results, repeated time points, 'ranging' that excludes results, 'condition out
of specification', mean change said twice, 'zero').

Second audit (same model, new checks and prompt rule): 116 accepted of 160. Read by hand: 92 ok, 20
awkward, 4 misleading, 0 wrong. Pass mark met (no 'wrong' in at least 100). The 4 misleading ones exposed
three more gaps ('decreased from the [[max]] to the [[min]]' with an article, 'remaining between the first
and last range' while a lower result existed, and the test name cut short), now closed. Those fixes
were made after seeing the drafts, so a third audit is the fresh test.

## Files

- `data/tasks.json`: the 8 synthetic sections, including one with an out-of-specification result
- `writer_test/facts.py`: computes every number and judgement, with regulatory rounding
- `writer_test/prompt.py`: the prompt; the model writes only the discussion paragraph
- `writer_test/validator.py`: the checks that reject a draft
- `writer_test/rendercheck.py`: re-reads the finished text against the raw table
- `writer_test/mutation_test.py`: plants errors and counts how many the checks catch
- `writer_test/run.py`: runs the drafts and writes the report
- `writer_test/compare.py`: blind rating against another model
- `tests/test_validator.py`: proves the validator catches each kind of error
