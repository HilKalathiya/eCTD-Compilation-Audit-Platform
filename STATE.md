# STATE (newest first; Claude Code keeps this <= 40 lines; Hil re-uploads it to the Claude Project after each milestone)

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

## 2026-11-01 — T-034 (C2.3 fix) done
- `chunk.SYMBOL_MAP` (shared by chunk.py and cite.py): U+F0A3 -> ≤, U+F0B1 -> ±, U+F0B7 -> bullet (only codes found in the 5 PDFs; the old map's 5 other entries never occur). `cite.normalise` maps them on page text and quote; "<" is still not "≤". `cite.MIN_QUOTE` = 40 chars. Running header/footer lines (same text, page number aside, on >= 50% of pages) are dropped from chunks (`chunk.running_lines`).
- Gold citations: 30 of 30 verify, MIN_VERIFIED = 28. Rerank recall 0.933 (hybrid 0.867, vector 0.900, fts 0.700). Misses: q22, q29.
- `watch.py`: write evidence for `X='path'` then open(X,'w')/X.write_text; same task id again keeps the original start. Known gap (needs a card): `load.store` never deletes chunks that no longer exist, so after a chunker change stale rows stay (I removed 20 once by script).

## 2026-11-01 — T-033 (C2.3) done
- `knowledge/cite.py`: `verify(doc_id, page, quote, pdf_dir=None)` -> `Citation(doc_id, version, page, quote, pdf_sha256)` or `CitationRejected(reason)`. Re-reads the page from the PDF with PyMuPDF (never kb_chunks); PDF sha256 must equal SOURCES.md; only whitespace collapse, end-of-line hyphen join, fi/fl ligatures, curly quotes are normalised. 15 tests in `tests/test_citations.py` (planted word, digit, wrong page, altered PDF bytes, wrong sha in SOURCES, empty quote all refused).
- Gold: first 200 chars of rerank top-1 verified for 26 of 30. Rejected: q02 (footnote marker order), q03/q04 (chunker turned Symbol-font U+F0B1 into a real +-), q29 (running header kept, page number inside it in the PDF). Real <= / +- signs are always refused (PDF stores U+F0A3/F0B1): pinned by a test; needs a card to decide.
- Helpers: `watch.py` run always prints the Ran/OK/FAILED lines (planted test: 30 lines after the summary). test-runner gets Monitor (tools exactly Bash, Read, Monitor; `test_agents.py` updated, Edit/Write/no-Monitor plants refused). `test_retrieval.RerankLiveTests`: real reranker, cache bypassed.

## 2026-11-01 — K7 (test-runner helper) done
- `.claude/agents/test-runner.md`: subagent, model haiku, tools exactly Bash + Read, runs the given test command (default `python tools/watch.py status --tests --timeout 900`) and replies in <= 10 lines; never edits, never git. CLAUDE.md rule now: "Subagents may not write code or tests. Only test-runner may be used, to run tests." `tests/test_agents.py` (6 tests; planted Edit tool / missing model / missing "never edit" all refused). Manual check by Hil pending (`/context` before/after).

## 2026-11-01 — T-032 (hook + rerank cache fix) done
- `watch.py log`: root cause of the T-031 gap = a lone surrogate (damaged em-dash) in the PowerShell input; the UTF-8 write raised and the bare `except: pass` hid it. Now such characters become `?`, and any other failure writes `LOGERROR <tool> <reason>`. Planted tests: multi-line PowerShell with a broken character, non-ASCII input, broken JSON.
- `knowledge/rerank.py`: scores cached in `.cache/rerank/` (gitignored), key = sha256(model + VERSION + question + passage text); changed passage, question, model or VERSION = miss. 6 cache tests (no database needed). Retrieval tests also embed each gold question once (lru_cache on `embed.embed_query`, same vectors). Full suite 752 s -> 270 s / 274 s (two runs, FLAGS none). CLAUDE.md: PowerShell/git line.

## 2026-11-01 — T-031 (C2.2b) done
- knowledge/rerank.py: sentence-transformers CrossEncoder mixedbread-ai/mxbai-rerank-base-v1 (CPU, float32, max_length 512, batch 16, loaded once per process; pinned sentence-transformers==6.2.0). search(q, mode="rerank") = FTS top 12 + vector top 12 (dedupe, <= 24 passages) -> rerank -> top 5. Cap is 24 not 40 because 40 took 16 s/question; 24 takes ~8-11 s. float16 (the default load) took 178 s/question: never use it.
- Gold recall@5: fts 0.667, vector 0.867, hybrid 0.800, rerank 0.933. Rerank misses: q22 (Q6A), q29 (M4Q_R1). Planted reversed-reranker test drops below vector. FTS query unchanged (websearch_to_tsquery not tried). Full retrieval test ~9 min.

## 2026-11-01 — T-030 (C0.3 fix) done
- `watch.py`: activity log keeps whole commands (cap 4000 chars, newline -> " ⏎ "); display cuts only when printing. "changed with no logged action" now needs real write evidence (Write/Edit target, or `>`/`tee`/Set-Content/open('w')/write_text/cp-mv-Copy-Item destination/git checkout --/git apply naming the file; deletes also count `rm`/`del`). `cat`/`grep` no longer count. Timeout exits 124. 6 new tests in `tests/test_watch.py`.

## 2026-11-01 — T-029 (C0.3 fix) done
- `watch.py`: test timeout default 900 s, `--timeout N` (works on `status --tests` and `run`); on timeout the whole process tree is killed and it prints `TIMEOUT - raise --timeout` (never EXIT 0). New FLAG `changed with no logged action: <file>` (file changed since task start, path absent from `.brain/activity.log`; only checked when the log exists). Log hook matcher now also covers PowerShell and NotebookEdit. CLAUDE.md: no subagents for code/tests unless the card says so. 3 new planted tests in `tests/test_watch.py`.

## 2026-11-01 — T-028 (C2.2a) done
- Migration 007: `kb_chunks.fts` (english tsvector, GIN) + `embedding vector(768)` (HNSW cosine) + `embedding_sha256` (cache key; a chunk is re-embedded only if its text hash changed). `knowledge/embed.py` (Ollama `embeddinggemma`, `python -m ectd_engine.knowledge.embed`), `knowledge/search.py`: `search(q, k=5, conn=None, mode)` -> `Quote(chunk_id, doc_id, page, table_id, text, score)`; RRF k=60 over FTS top 20 (any question word, ts_rank_cd) + vector top 20. Quote has no value field.
- Gold (30 Qs, `tests/gold/retrieval_gold.json`, sha c04bf734..): recall@5 hybrid 0.800, FTS-only 0.667, vector-only 0.867. Misses (hybrid): q02 q05 q18 q22 q23 q29. Hybrid is on the pass line, below vector-only; reranker is T-031. 5 live tests in `tests/test_retrieval.py` incl. planted `kb=` locator refused by the gate. First embed of 505 chunks takes ~3 min.

## 2026-10-31 — K6 done
- Engine rules (Decimal only, no `float()`/`round()`, values via fact-store API) moved from CLAUDE.md to `.claude/rules/engine.md` (`paths: ectd_engine/**`). CLAUDE.md now has one pointer line. 5 tests in `tests/test_rules.py`.

## 2026-10-31 — T-027 (C2.1) done
- ICH Step-4 PDFs (M4Q(R1), Q1A(R2), Q1E, Q3B(R2), Q6A) in `data/public/ich/` (SOURCES.md has URL, date, sha256). `ectd_engine/knowledge/chunk.py`: ~800-char text chunks on paragraph/heading boundaries (never across pages); tables as one chunk each (ruled via find_tables, borderless via word gaps), cut only between rows if > 1500 chars; ids `<doc>:p<page>-c<n>` / `table_id p<page>-t<n>`; Symbol-font characters (≤ ≥ ±) mapped to real ones.
- Migration 006 `kb_chunks` (no value column; page is the only number). `python -m ectd_engine.knowledge.load [--dry-run]`; reload is idempotent. 21 tests in `tests/test_ich_chunks.py` (3 Q3B threshold tables complete; planted missing row / page 0 / no doc refused; live reload no duplicates). Q1E has no real table: its decision tree (p12) is a drawing, kept as text chunks.

## 2026-10-30 — T-026 (C1 fix) done
- `migrate` now records each migration file in table `schema_migrations` (filename, sha256, applied_at) and runs only unrecorded files, each in its own transaction. An old DB without the table gets 001-004 recorded without re-running. A recorded file whose text changed -> error "migration edited after it ran". Migration 005 creates the table. The T-025 CheckViolation bug is fixed; `demo_facts` now migrates first, then wipes only its own rows. `tests/test_migrate.py`: 3 live tests (incl. planted edit).

## 2026-10-30 — T-025 (A0) done
- `python -m ectd_engine.demo_facts` loads Lek (4965 accepted, 60 quarantined), Kerendia PDF (8) and DailyMed label (5) into live Postgres + Neo4j through the gate under the id prefix `DEMO25-` (nothing else is touched), plants one bad Lek row, prints 5 PROOF lines (Lek CSV row, Kerendia page+box, label version change v1 20 mg vs v12 40 mg, planted row quarantined, compare() == []); exit 0 only if all hold. `--clean` removes the demo data. ~70 s.
- 3 live tests in `tests/test_demo_facts.py` (databases down -> FAIL "start Docker"; planted graph edit -> proof 5 fails, exit 1). Known bug (not fixed, needs a card): `migrate` re-run fails with CheckViolation when rows with `xml=`/`typed=` locators exist, because migration 002 re-adds the older locator rule before 004; the demo wipes its rows before migrating and the test cleans up.

## 2026-10-30 — T-024 done
- Outside check: `tests/test_r_crosscheck.py` (9 tests) runs R expirest 0.1.7 via `tests/r/q1e.R`: pooling decision equal for cases a/b/c, shelf life (and per-batch) equal within 0.01 month; single-batch assay (lower) and impurity (upper) too. NIST Norris.dat: slope, intercept, residual SD match to 15 digits.
- Flaky hunt: full suite 6 runs, 0 failures, no random/time use in tests. R 4.6.1 installed with winget; expirest lives in the per-user folder Documents-independent `~/R/win-library/4.6` (the test sets R_LIBS_USER itself). Missing R makes the test FAIL ("install R"). expirest does not apply our extrapolation cap; all cases are uncapped.
