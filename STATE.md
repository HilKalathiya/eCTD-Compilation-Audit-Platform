# STATE (newest first; Claude Code keeps this <= 40 lines; Hil re-uploads it to the Claude Project after each milestone)

## 2026-11-20 — T-053 done (C3.6a: code decides the P.5 content; every number has a placement)
- `ectd_engine/render/`: `plan.py` (CONTENT_PLAN for P.5.4 + P.5.6, required fact keys per section), `numbers.py` (one number-finder + 3 exempt kinds: guideline/section names, batch ids in text, batch-id table cell), `html.py` (build, placements, gates "missing:<key>" and "unplaced:<text>"). `tools/render_doc.py --out evidence/T-053/` -> P5.html, placements.jsonl, report.txt.
- Real run: 3589 numbers = 3589 placements = 3589 data-src, 540 sections, missing 0. Inputs: T-042 (P.5.4, 130 accepted) and T-048 (P.5.6, 150 incl. 21 synthetic). Placement ids are fact keys (limit, q3b_quote ...) or LEK-<batch>-<column> for table cells. `tests/test_render.py`: 23 tests incl. planted gates.

## 2026-11-19 — T-052 done (suite 556 s -> 266 s, same 581 tests, same assertions)
- `tools/test_times.py` (per-test seconds CSV). Setup-only helpers in `tests/`: `fast_localhost` (localhost -> IPv4; saved ~2 s per Ollama connection), `chunk_cache` (PDFs chunked once per run), `warm_models` (torch import in a background thread); `test_watch.py` builds its template repo once. Table: `evidence/T-052/changes.md`; `before.csv`/`after.csv`.
- Not reducible here: 3 demo runs (~140 s, engine DB writes) and 6 db_down timeouts (5 s each, they test the timeout).

## 2026-11-19 — T-051 done (prose rules are a gate on live output; audit count tamper uses digits)
- `ectd_engine/writer/spec_prose.py`: `PROSE_RULES` (12 named rules) + `prose_problems`, the one source for the loop, tests and evidence. `spec_loop.py`: after render, any hit rejects the draft with "prose:<rule>" (planted bad draft test). Validator untouched.
- `tools/audit_p56.py`: count tamper now writes digits ("9 batches" -> "10 batches"; whole-word match); `expected_task` expects only the dose-row quote (T-049 would have made the re-read flag every real Q3B paragraph). Tests: every tamper kind made and caught for n = 1, 2, 9, 12, 60.
- 150 re-rendered paragraphs: 0 prose rejects, 0 re-read problems (`evidence/T-051/hits.txt`).

## 2026-11-19 — T-050 (FIX for T-049) done (digit counts, verb agreement, any basis lead-in repaired)
- `spec_facts.py`: `render_paragraph` now rewrites ANY words between `[[limit]]` and `[[basis]]` of a declared limit to ", which is [[basis]]" (w128 and s012 "resting upon" fixed); counts are always digits ("Results for 9 batches", "2 of 9 results"); "1 of 24 results was", "2 of 24 results were". Validator untouched.
- Tests: new prose rules (upon, number word as a count, 1 of N were, N>1 of M was) each with a planted test; 150 re-rendered paragraphs: 0 hits per rule (`evidence/T-050/hits.txt`, `rendered.md`).
- Open: `tools/audit_p56.py` (blind-sheet planting) still replaces `count_text(n)` (words) in rendered text; with digit counts that step can no longer find small counts. Needs its own card.

## 2026-11-19 — T-049 (FIX C3.5 prose) done (grammar + one-row Q3B quote; Hil's findings are tests)
- T-048 blind score: 3/3 planted caught, 22/22 agree, SCORE PASS (commit 00e0ab4).
- `spec_facts.py`: `render_paragraph` (counts read "17 of 25 results", declared basis reads ", which is ..."), `q3b_row_quote`/`narrow_quote` (quote = only the dose-band row, re-verified with `cite.verify`, page kept); `check_task` rejects any other quote. Prompt rule 4 words the basis. Validator untouched. Evidence: `evidence/T-049/rendered.md` (150 re-rendered paragraphs, no model).
- Tests: B11/B16/B17/B25 regression tests, planted wrong-band quote, 150-paragraph re-render check; mutation test still 100%.

## 2026-11-19 — T-048 (FIX C3.5b) done (exact 3-sentence prompt, required outside-count sentence, Gemma audit)
- `spec_prompt.py`: "exactly 3 sentences" (limit+basis, range, outside count) with one example per basis. `validator/spec.py`: ONE new rule `outside_statement_problems` (no sentence saying how many were outside -> reject); nothing removed or relaxed; 3-6 range stays. Mutation kind `omit_outside_statement` caught 100%; T-047's 520 drafts replayed: 0 accepted.
- Gemma audit (`writer_run.py --kind p56 --audit 130 --synthetic 26`): real 129/130 accepted, re-read wrong 0; synthetic (n_outside>0, declared attributes, own limit) 21/26, wrong 0. Synthetic windows live in `run/.../synthetic/`, so blind.csv (25 rows, 3 planted) is from real windows only. Details: `evidence/T-048/SUMMARY.md`.
- Open: Hil must label blind.csv, then `audit_p56.py --score`. Wording "2 batches of 7 batches results" reads badly (card's exact sentence + count_text).

## 2026-11-19 — T-047 (C3.5b-2) PARTIAL (tools + tests done; real-Gemma audit accepted 0/130, brain must decide)
- `python tools/writer_run.py --kind p56 --audit 130 --backend ollama --model gemma4:e4b --out evidence/T-047/run`: 130 fixed-seed windows (8-30 real Lek batches each, 5 attributes in turn, some with quarantined batches). Result: 0/130 accepted, 4 drafts each (2773 s). Every final draft broke one rule: "needs 3-6 sentences, got 2" (2 also: "declared limit written like a sourced one"). Cause: when n_outside = 0 the model writes 2 sentences (copies the declared example); the validator needs >= 3 and the prompt only says "you may" add the no-result-outside sentence. Fix belongs in `validator/spec.py` or `spec_prompt.py` (not touched, per card).
- Re-read of accepted = n/a (none accepted). `tools/audit_p56.py` stops with "no accepted declared-basis paragraph" and writes no blind sheet, so blind.csv / Hil's score are NOT done. Files: `evidence/T-047/audit.csv`, run folder (tasks.json, results.jsonl, drafts.jsonl).
- `tools/writer_run.py --kind p56 --audit N` added; `tools/audit_p56.py` (re-read from stored facts, blind sheet 22 real + 3 planted wrong, `--score` PASS only if Hil catches all 3 and agrees on the 22); 15 mock tests in `tests/test_audit_p56.py`.
- Full suite: 557 tests OK (519 s). FLAGS: only the unlogged run files.

## 2026-11-15 — T-046 (C3.5b-1) done (P.5.6 justification writer + spec validator, mock only)
- `writer/spec_{facts,prompt,loop}.py`, `validator/spec.py` (own word lists; declared limit = no source wording; q3b = `[[mdd]]` + "assumed" in the same sentence; compliance wording only if n_outside = 0; safety/"qualified" always rejected; Q3B quote only from `[[q3b_quote]]`; `verify_render` re-reads the finished text, incl. the exact Q3B name). `data/tasks/p56_tasks.json`: 5 real + 5 planted variants. `python tools/writer_run.py --kind p56 --backend mock` -> 5/5. Runner re-reads live numbers and quotes; a stale task file is refused.
- `tests/test_mutation_spec.py`: 28 draft kinds + 5 rendered-text kinds, 610 tasks: caught 9816/9816; correct accepted 610/610 (+ re-read 610/610, 9/9 paraphrases); hand-written wrong 12/12. `tests/test_spec_writer.py`: 20 tests.
- Re-read found a real gap during the work (a changed "Q3B" inside the basis wording passed); fixed.
- Full suite: 542 tests OK (833 s) on rerun. First run: 1 error, not identified (output cut); did not repeat.

## 2026-11-15 — T-045 (FIX) done (every Postgres/Neo4j connect in the engine is timed, 5 s)
- `db/postgres.connect` (connect_timeout=5) and `db/graph.connect` (Neo4j timeouts 5 s) now raise `store.DatabaseDown` with the start command; they reuse `CONNECT_TIMEOUT`/`DatabaseDown` from `facts/store.py`. T-044 gap closed. `tests/test_db_down.py`: 4 more planted tests (closed + silent port each).
- Full suite: EXIT 0, 516 tests, 541 s, FLAGS none. `facts_graph.connect` keeps its own copy of the Neo4j logic (outside this card).

## 2026-11-15 — T-044 (FIX) done (suite finishes again; a stopped database fails fast and loud)
- Cause: Docker Desktop was stopped, so every Postgres connect waited ~260 s (tests.test_graph alone: 260.0 s; after start: 4.2 s). Neo4j is a separate profile (`graph`), it was also stopped.
- `store.connect_app` (Postgres connect_timeout=5) and new `facts_graph.connect` (Neo4j timeouts 5 s) raise `store.DatabaseDown` naming the service + the start command; `knowledge/load.py` sets PGCONNECT_TIMEOUT=5 and exits with a clear message. `tests/test_db_down.py` (4 planted tests: closed port and silent port, each < 15 s).
- Full suite: EXIT 0, 512 tests, 479 s, FLAGS none (T-043 PARTIAL -> done). Gap: `db/postgres.py` and `db/graph.py` (used by most tests) still have no timeout; they were outside this card.

## 2026-11-15 — T-043 (C3.5a) done (suite green, see T-044) (Lek spec facts + P.5.1 table + P.5.6 justification facts, no model)
- Open: `watch.py status --tests` hit its limit twice (900 s, then 1500 s, EXIT 124); FLAGS: none. The 13 new tests pass alone (0.05 s). Whether the full suite passes is not shown; slow modules are being timed.
- `ectd_engine/specs/`: `load.py` (spec CSV -> gated facts `SPEC-LEK-<attr>` + `ASSUMPTION-MDD` = 40 mg; q3b rows computed by `q3b.threshold("qualification", 40)` = 0.5% (rule Q3B_R2@2006-06-02:qualification:2, page 11), typed value in a q3b row or a source claim in a declared row = refused; declared rows get lineage unknown and DECLARED definition), `p51.py` (P.5.1 table by code; missing fact = refuse and name it), `p56.py` (basis, Q3B quote re-verified on the PDF with page, n/min/max/outside per attribute via `stats.basic.conforms`).
- Real Lek (accepted batches): n 985-1005, outside limit 0 for all 5 attributes. `python -m ectd_engine.specs.p56` prints it all.
- `tests/test_specs.py` 13 tests incl. planted: MDD 40->5 mg changes rule and limit, typed q3b value, declared claiming Q3B, altered quote, missing fact, batch outside limit.
- ChemR (`kerendia/215341Orig1s000ChemR.pdf`): limits are hidden by "(b)(4)" (107 marks; page 28 reads "NLT  % (Q) in  min"); no numeric spec limit visible on any page.

## 2026-11-03 — T-042 (C3.4b) done (real-Gemma audit of the P.5.4 writer)
- `python tools/writer_run.py --kind p54 --audit 130 --backend ollama --model gemma4:e4b --out evidence/T-042/run`: 130 fixed-seed windows of 12 real Lek batches (seed 42, 26 per attribute, 52 with a quarantined batch). Result: 130/130 accepted (127 on draft 1, 3 on draft 3 or 2; 135 drafts in all, 850 s). No final rejects, so no false-reject rate from final drafts; 5 retried drafts all hit one rule ("exclusion wording applied to [[n_batches]]", sentence "...analyzed, with [[n_excluded]]... quarantined"). Brain decides if that rule is too broad.
- `tools/audit_p54.py` re-reads each accepted section against the table rebuilt from the stored facts: wrong = 0 of 130. Files in `evidence/T-042/`: audit.csv, summary.md, blind.csv (25 rows, Hil fills `hil_label` right/wrong), blind_key.csv. `python tools/audit_p54.py --score --run <run folder> --out evidence/T-042` compares Hil's labels (empty/odd label = error, exit 2).
- 12 tests in `tests/test_audit_p54.py` (mock only; planted changed number and changed fact are labelled wrong; missing labels stop the run).
- Limit: the re-read uses the same `verify_render` as the writer loop, with the table rebuilt from the store; Hil's blind labels are the truly independent part.
- Blind score (`audit_p54.py --score`): Hil labelled 25 sections: wrong = 0 []; differs from the re-read = 0.

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
