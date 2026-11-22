---
name: p83-stability
description: Write the 3.2.P.8.3 stability paragraphs (one public paragraph plus one per condition x attribute) with a local model; code writes every number and a validator checks every sentence. Use when asked to draft or re-run the P.8.3 stability text.
---

# p83-stability

## When to use
- You need the P.8.3 stability text drafted or re-checked from `data/stability/finerenone_stability.csv`.
- Do NOT use it for P.5.4 or P.5.6 text, or to change the stability data or its checks.

## Inputs
- The stability CSV (default `data/stability/finerenone_stability.csv`; 6 public rows, 60 DEMO rows). For the held-out test add `--heldout --data evidence/T-065/heldout.csv` (made-up data, 20 tasks, some results outside the limit).
- A model: `--backend mock` (no model) or `--backend ollama --model gemma4:e4b` (Ollama on localhost:11434).
- `--out <folder>`: where the drafts and sections go (required; use a new folder).

## Steps
1. Run `python skills/p83-stability/scripts/run.py --backend ollama --model gemma4:e4b --temperature 0 --seed 42 --out <folder>`.
   It calls the same entry point as `python tools/writer_run.py --kind p83 ...`, so the verdicts are identical. A `--out` folder that already holds a run is refused (use a new folder each time).
2. The model writes `[[slot]]` placeholders only. Code fills in the numbers and checks each sentence (`ectd_engine/validator/stability.py`); a rejected draft is sent back with the problems, up to 4 drafts.
3. Read `<folder>/summary.json` (accepted count, wrong_accepted must be empty) and `<folder>/sections/*.md`.
4. To prove a skill run equals a direct run: `python -m ectd_engine.stability.compare <direct folder> <skill folder> --out compare.md` (exit code 1 = a verdict differs).

## Rules
- Demonstration rows are always labelled "In illustrative demonstration data". Never remove the label.
- Never edit a number by hand; fix the facts or the data, and re-run.
