# STATE (newest first; Claude Code keeps this <= 40 lines; Hil re-uploads it to the Claude Project after each milestone)

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

## 2026-10-30 — K5 done
- `/where`, `/explain`, `/recap` moved to `.claude/skills/<name>/SKILL.md` (text unchanged, disable-model-invocation true); new `/verify` (allowed-tools only `Bash(python tools/watch.py *)`) runs `watch.py status --tests`. `.claude/commands/` removed. 8 tests in `tests/test_skills.py`. Restart Claude Code to see the 4 skills.

## 2026-10-30 — T-023 done
- `ectd_engine/stats/oot.py`: `check(history, (month, value), level=0.99)` -> OK | OOT (with low/high) | NotEnoughData (< 3 points or all same month); uses the two-sided PREDICTION interval (`interval`). `check_with_policy` returns (result, note).
- `ectd_engine/stats/loq.py`: `parse` ("<LOQ", "<0.05", "ND" -> Below), `Policy` EXCLUDE (default) / REPORT_ONLY / SUBSTITUTE (needs value + reason, else ValueError), `apply_policy`, `shelf_life_with_policy` -> (ShelfLife or None, note). 22 tests in `tests/test_oot_loq.py`; PI matches statsmodels to 10 digits. q1e.py/tdist.py unchanged. Suite 226 OK.

