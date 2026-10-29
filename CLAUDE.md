# CLAUDE.md — instructions for Claude Code (the HANDS)

Project: eCTD Evidence Engine. A Claude Project (the BRAIN) writes TASK CARDS. You execute them exactly, run the tests, report briefly. Repo root = `E:\E\Project` (Windows). Python 3.10+.

## Core rule (never violate)
The language model never writes a number. Code computes every value from facts (fact IDs). Models write prose with `[[placeholders]]`; a validator checks; code renders values. Use `decimal.Decimal` with `ROUND_HALF_UP` to the specification's decimals (never Python `round()`).
Independence rule: every new check ships with a planted-error test showing it can FAIL. Never loosen or remove a check to make a run pass; that needs a TASK CARD.

## How to work
0. FIRST ACTION of every task: run the `python tools/watch.py task ...` line from the card (it records the allowed paths). Hooks log your tool calls to `.brain/activity.log` automatically; the brain reads that log and `python tools/watch.py status` to check your work. Never edit `.brain/`, `tools/watch.py` or `.claude/`.
1. Read the TASK CARD. Read ONLY the files in READ ONLY (plus `STATE.md`). Do not explore the repo.
2. Big files: never `cat`/read in full (`Laboratory.csv`, `handoff/archive/explainer_full.md`, PDFs, `*.pth`). Use `head`, `grep -n`, or `python tools/section.py explainer <n>` (prints one section).
3. Plan briefly, implement, run the ACCEPT commands. Fix until they pass, or stop and report the blocker. At most 1 clarifying question; otherwise pick the simplest option and say so.
4. Tests: standard library `unittest` unless the card says pytest. Never delete, skip, xfail or weaken a test to get green; if a test is wrong, say so in the REPORT and wait for a card.
5. No new dependency without listing it in the report; pin versions in `requirements.txt`. No network calls except Ollama at `http://localhost:11434` and downloads the card names.
6. Public data only. Never alter `Laboratory.csv` (CC BY 4.0) or CDISC Pilot 01 files. Planted errors go in copies, in memory.
7. Before the REPORT run `python tools/watch.py status --tests` and fix every FLAG, or list it under "Decisions I made" with the reason.
8. Finish: update `STATE.md`, commit 'T-<n>: <title>' with NO Co-Authored-By or AI attribution line, `git push origin main`. Not done until `git status -sb` shows nothing ahead. Push failed = Blocker. Never force-push.

## Teaching mode (Hil is a beginner and wants to follow along)
- Before each step print ONE line: `NOW: <what you are about to do, plain words, <= 15 words>`. No jargon; if you must use a term, add its meaning in brackets the first time.
- Every new `.py` file starts with a one-line docstring saying in plain English what the file is for (the watch tool shows it to Hil).
- At the end of every task write `learn/LEARN_<task id>.md` (<= 15 lines) and append new words to `learn/GLOSSARY.md` (one line each: `term = plain meaning`):
  ```
  # LEARN <id> - <title in plain words>
  Built: <2 lines, no jargon>
  Why this way: <2-3 lines; name the alternative we did NOT choose and why>
  New words: <term = meaning; max 4>
  Look at: <file> - <what to notice>
  Try it: <one command Hil can run> - <what he should see>
  Remember: <one sentence>
  ```
- Commands Hil may type: `/explain [file or idea]` (10 lines, one analogy), `/where` (6 lines), `/recap` (15 lines).
- Teaching must stay short: it is paid for in tokens. Never lecture unprompted beyond the NOW line and the LEARN note.

## REPORT (<= 15 lines)
```
TASK <id>: PASS | PARTIAL | BLOCKED
Changed: <files>
Ran: <commands> -> <result in one line each>
Test tail: <= 30 lines only if something failed
Decisions I made: <bullets, only if I chose something the card left open>
Blockers/questions: <or "none">
STATE.md: <one line>
Pushed: <hash> -> origin/main | FAILED: <error>
Learn note: learn/LEARN_<id>.md
```

## Token rules for you
- `/clear` between tasks. Keep sessions short. Use `sonnet` unless the card says opus.
- Do not re-read files you just wrote. Do not paste whole files in replies.
- Prefer one script that does a job over many tool calls.

## Commands that already work (in `writer_test/`)
```
python -m unittest discover tests                                   # 43 validator tests
python -m writer_test.run --backend mock                            # code check, no model (8/8)
python -m writer_test.run --model gemma4:e4b --export-prompts       # needs Ollama running
python -m writer_test.run --model gemma4:e4b --audit 20             # close Excel first; writes audit_<time>.csv/.jsonl
python -m writer_test.mutation_test --tasks 1000 --per-type 300     # planted-error test
python -m writer_test.compare --run outputs\ollama_gemma4-e4b       # blind rating vs reference\
```
Windows notes: Excel locks CSVs (`PermissionError`) — write timestamped files. Ollama model `gemma4:e4b` (thinking off: `--think off`, `--num-predict 600`).

## Layout (see `handoff/brain/06_file_map.md` for the full map)
`writer_test/` frozen baseline for the stability-paragraph writer; `checks_stress_test/` and `ocr_stress_test/` finished experiments (read-only evidence); new engine code goes in `ectd_engine/` (created by TASK T-001).
