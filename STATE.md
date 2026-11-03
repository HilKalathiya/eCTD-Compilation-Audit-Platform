# STATE (newest first; Claude Code keeps this <= 40 lines; Hil re-uploads it to the Claude Project after each milestone)

## 2026-11-03 — T-041 (C3.4a) done (3.2.P.5.4 batch analyses writer on Lek facts)
- Code computes everything, the model writes one paragraph with `[[placeholders]]`: `ectd_engine/writer/batch_facts.py` (n, n_excluded, lowest/highest with ALL tying batch ids, mean via `stats/basic` half-up, table rows; reads through a `get_fact(id)` + batch registry; unknown batch id = loud error, quarantined = excluded; source values never rounded, task `decimals` must cover them), `batch_prompt.py` (model never sees the table), `batch_loop.py` (retry loop + fake model; extra file inside the allowed `batch_*.py` glob), `validator/batch.py` (own word lists: compliance/spec words rejected because Lek has no spec fact, batch-count words, mean-as-range, range order, exclusion iff n_excluded > 0; plus an independent re-read `verify_render` of the finished text vs the raw table). `validator.py` untouched.
- `data/tasks/p54_tasks.json`: 6 tasks (5 Lek attributes over batches 1-12, + Total impurities with batch 60 quarantined). `python tools/writer_run.py --kind p54 --backend mock --out <dir>` -> 6/6 accepted (draft 1 wrong, draft 2 right). `tools/replay.py` now has argparse (`--help`, `--out`).
- Tests: `tests/test_batch_writer.py` (32), `tests/test_mutation_batch.py`: 21 draft kinds + 6 rendered-text kinds over 700 tasks (400 real Lek windows, 277 with excluded batches); each planted error must be caught by the rule meant for it: 7884/7884; correct text accepted 700/700 (+ re-read 700/700); a planted gap (compliance list disabled) is reported as a miss.
- Full suite: 483 tests OK (494 s), FLAGS none.
- Known limit: P.5.4 reads Lek through `LoaderStore` (runs the real loader against a recorder, no database); production passes `store.get`.

## 2026-11-02 — T-040 (C3.3) done (round-3 drafts replayed through the port)
- `python tools/replay.py` runs every saved draft through the frozen validator (writer_test, read-only) and `ectd_engine`'s: same verdict and same sorted problem list required. Result: 171 drafts, 171 same, 0 different (111 accepted, 60 rejected). Sources: `audit_20261029_135323.jsonl` (160 = round-3 audit) + `drafts.jsonl` (11). Rounds 1-2 audits and the 2-row aborted `audit_20261029_133616.jsonl` are not included. Per-draft table: `evidence/T-040/replay.csv`.
- 6 tests in `tests/test_replay.py` incl. planted flipped verdict (reports 1 different, exit 1) and missing/empty draft file (exit 2, no 0/0 pass).
- T-039 laptop: gemma4:e4b 8/8 accepted, 94 s, lt_dissolution 3 drafts (files in `evidence/T-039_laptop/`).

## 2026-11-02 — T-039 (C3.2) done (engine LLM client + structured outputs)
- `ectd_engine/writer/llm.py` (Ollama /api/chat, OpenAI /chat/completions, Mock; stdlib only; optional `schema=` sends Ollama `format` / OpenAI `response_format`), `prompt.py` (copy of the frozen one, import only), `loop.py` (`run_task`: draft -> validator -> re-read of finished text -> retry, max 4; returns accepted + every draft + rendered text), `structured.py` (own schema check; a value is accepted only if schema fits AND text/number appears word for word in the source; numbers parsed as Decimal). `tools/writer_run.py --backend ollama|openai|mock`.
- Mock: writer_test 8/8, engine 8/8 (2 drafts each in both). 17 tests in `tests/test_writer_llm.py` (planted: raw number, schema break, value not in source, number inside "B2"; fake local HTTP server checks both payload shapes). Not yet run against a real model (laptop run is Hil's).

## 2026-11-02 — T-038 (C3.1) done (validator ported into the engine)
- Ported from `writer_test/` (left untouched): `ectd_engine/writer/facts.py` (Decimal everywhere: `to_decimal`, `decimal_task`, `tolerance`; no float/round), `ectd_engine/validator/validator.py` (byte-identical), `ectd_engine/validator/rendercheck.py` (import only). Not ported: prompt.py (the ported test reads it from the frozen folder).
- Original vs port: 43 tests -> 43 (`tests/test_validator_port.py`, same names and assertions); mutation test 8303/8303 caught -> 8303/8303 (`tests/test_mutation_port.py`, report identical line for line; +4 wrapper tests that fail if any mutant survives or the kill count drops). Line-by-line diff report in `learn/LEARN_T-038.md`.
- Open: facts are still computed from a task dict, not read through the fact-store API; the writer card must connect them. Full suite: 422 tests OK (461 s), FLAGS none.

## 2026-11-02 — T-037 (C2.4) done (Q3B threshold table, double entry)
- `data/rules/q3b_entry_a.csv` (typed from PDF p11) and Hil's `q3b_entry_b.csv` agree on all 10 rows (0 differences). `ectd_engine/rules/q3b.py`: `load()` refuses on any A/B difference, any row not word for word on Q3B p11 (`cite.verify`), or a gap/overlap in dose ranges; `threshold(kind, dose_mg, version="latest")` -> (percent, tdi_ug|None, rule_id), Decimal only, boundaries as printed; refuses if a typed file changed after load.
- Migration 008 `rule_thresholds` (append-only trigger; a new doc_version adds rows). `store()` refuses same rule_id with other content. 19 tests in `tests/test_rules_q3b.py` incl. planted: row only in A/B, 0.1 vs 0.15, <= vs <, tdi differs, same typo in both (PDF check fails), dropped row, edited entry_b after load.

## 2026-11-02 — T-036 (fix) done (watcher: no false green when git fails)
- `tools/watch.py git()`: a failed call (non-zero exit or OSError) is retried 3 times, then raises `GitError`. `status` prints `GIT ERROR: <command> -> <message>`, `FLAGS: 1`, `! git failed - result unknown`, exit 2; `task` prints GIT ERROR, exit 2. "No commits yet" and "not a repo" are still normal answers (matched on git's message, run with LC_ALL=C).
- `tests/test_watch.py`: new `GitFailureTests` (8 tests): always-failing git, git cannot start, only `diff` failing, one failure then success, clean real repo, no-commits repo, non-repo folder, `task`.

## 2026-11-02 — T-035 (fix) done
- `tests/test_watch.py`: temp git repos are built by `build_repo`/`git_retry` (3 tries, local author, base commit checked; also retries WinError 5). `status()` asks again if the watcher says 0 changed files while git shows changes. 5 helper tests added.
- `load.store()`: one transaction; upserts a document's chunks and deletes that document's rows not in the new set; other documents untouched; rollback on error. 4 new tests in `test_ich_chunks.py`.
- Open: `tools/watch.py git()` hides failed git calls (prints 0 changed); needs its own card. Suite: 348 tests, 3 clean runs in a row.
