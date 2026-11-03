# STATE archive (older entries moved out of STATE.md, original order)

## 2026-10-30 — T-019 done
- `python -m ectd_engine.loaders.dailymed --dry-run`: Kerendia label XML (set id fc726765-…) v1 (2021-07-09: 10, 20 mg) and v12 (2025-07-29: 10, 20, 40 mg) -> 5 `Strength` facts, all accepted, locator `xml=/document/.../numerator[1]` (the value sits in its `value` attribute). XML + sha256 in `data/public/kerendia/` (SOURCES.md). The DailyMed `.xml?version=N` URL ignores N; the `getFile.cfm?type=zip&version=N` URL works.
- `agree()` now also returns ReviewItem kind `version change` (same doc_id, different doc_version, different values, both versions cited) and `copy disagrees` (copy/unknown differs from the original). Two different docs disagreeing is still `conflict`. 160 tests OK.

## 2026-10-30 — T-018 done
- Locator forms now 5: row, page+box, cell, `xml=/path`, `typed=page=N` (schema.py + migration 004, same verdicts; live test compares both). double_entry.py now emits `typed=page=N` (no fake box, no float). 148 tests pass, live locator test ran.

## 2026-10-30 — T-017 done
- units.json + ranges.json now cover Shelf life, Accelerated stability duration, Strength, Maximum daily dose, Dissolution paddle speed, Dissolution medium volume (match ranges_check.json after Hil fixed the "Maximun" typo). `fda_pdf --dry-run` -> 8 accepted, 0 quarantined.
- `python -m ectd_engine.loaders.double_entry <fact_key>`: blind double typing (getpass); match as Decimal -> candidate (lineage original, "typed twice"), else REFUSED. Locator box is 0,0,0,0 (word box not located). 143 tests pass.

## 2026-10-29 — T-016 done
- `python -m ectd_engine.loaders.fda_pdf --dry-run`: 8 facts from the Kerendia chemistry review (NDA 215341, 36 pages, all with text) with locator `page=N;box=...`; targets in `loaders/kerendia_targets.json`. PDF + sha256 in `data/public/` (SOURCES.md). pymupdf==1.27.2.3 added. All 8 quarantine (TEST_UNKNOWN) until the 6 new tests get units+ranges (Hil types ranges_check.json first); units.json/ranges.json NOT edited (test_gate needs them to match ranges_check). 10 tests in `tests/test_fda_pdf.py`.

## 2026-10-29 — T-014 done
- Evidence graph: `gate.submit(..., graph=None)` also writes accepted facts to Neo4j via `ectd_engine/graph/facts_graph.py` (`put_fact`, `read_all`; nodes Fact/Batch/Source, all values as text). Quarantined or store-refused facts never reach the graph.
- `graph/compare.py`: `read_postgres`, `compare(pg, graph)` -> mismatches (missing_in_graph / missing_in_postgres / field_differs; "0.140" != "0.14"). 11 tests in `tests/test_graph.py` (1 live, ran). If the graph write fails after Postgres committed, the error propagates and compare shows the drift.

## 2026-10-29 — T-013 done
- Gate part b: `ectd_engine/gate/agree.py` `agree(facts)` for one (batch, test, condition, month) -> Verified | SingleSource | Conflict (ReviewItem kind "conflict", both values + sources). Routes = distinct doc_id among lineage "original"; copy/unknown never count; originals that disagree as Decimal -> Conflict; mixed keys or empty -> ValueError.
- `drift(stored_fact, reread_value)` -> None if equal as Decimal, else ReviewItem "source changed". Pure functions, no DB (saving review items waits for C1.5). 10 tests in `tests/test_agree.py`; 107 tests OK. 0.14 vs 0.014 gap from T-011 now catchable once agree() is wired in.

## 2026-10-29 — T-012 done
- `gate.load_rules` now compares `ranges.json` vs `ranges_check.json` as {test: (Decimal min, Decimal max)}: "1" == "1.0", "5.1" != "5.0", extra test name or non-number -> ValueError. New helper `gate.range_limits`. 4 new planted tests in `tests/test_gate.py`; 97 tests OK (fixes the red test_gate noted under K3).

## 2026-10-29 — T-011 done
- Write gate part a: `ectd_engine/gate/gate.py` `submit(candidate, batch_registry, conn)` -> Accepted | Quarantined. Order: contract, batch, unit (table conversion only), range. Rules in `gate/rules/` (`ranges.json` + `ranges_check.json` must be identical, loader refuses otherwise).
- `003_quarantine.sql`: table `gate_quarantine_rows` + `gate_quarantine()` (ectd_app EXECUTE only); non-blank checks now `~ '[^[:space:]]'`; Python Fact requires non-blank definition. Codes: FIELD_MISSING, CONTRACT_INVALID, BATCH_UNKNOWN, TEST_UNKNOWN, UNIT_NOT_ALLOWED, RANGE_OUT, STORE_REFUSED.
- Known gap: 0.14 -> 0.014 passes (needs C1.4 two-route agreement). Rule values (5 tests) are placeholders, to be confirmed by Hil.

## 2026-10-29 — T-010 done
- `002_gate_checks.sql`: 13 named CHECK constraints on `facts` (non-blank text, finite value, plain value_text, month >= 0, lineage, locator form). `tests_live/test_gate_checks.py` calls the gate directly as `ectd_app` with 9 bad inputs (all refused) + a drift test tying schema.py checks to constraint names. 30 live tests.
- Note: DB also requires non-blank `definition`; Python's Fact does not (card asked for it). Value `1E+2`/Arabic digits are caught by the gate's value_text=value::text rule first.

## 2026-10-29 — T-009 done
- Facts live in Postgres table `facts`; login `ectd_app` (password in git-ignored `.env`: APP_DB_USER/APP_DB_PASSWORD) can only SELECT and call `gate_insert_fact` (SECURITY DEFINER). Direct INSERT/UPDATE/DELETE = permission denied. `python -m ectd_engine.db.migrate` is idempotent.
- `ectd_engine/facts/store.py` put/get keep "0.140" exact. Schema now refuses exponent Decimals (1E+2) and uses [0-9] not \d. Removed tracked `.claude/settings.backup.json`. 63 unit + 17 live tests.

## 2026-10-29 — T-008 done
- Fact box tightened: batch/condition non-empty ("n/a" allowed), value text must be plain `-?\d+(\.\d+)?`, unknown JSON keys refused. 56 tests.
- Round-3 audit: 160 drafts, 49 rejected, 111 accepted: 92 ok / 19 awkward / 0 misleading / 0 wrong. The one "out of specification" note (acc_impurity_b_oos draft 13): B3 Month 6 = 0.18 > NMT 0.15, so facts say fails -> row is awkward, not wrong.

## 2026-10-29 — T-007 done
- `ectd_engine/facts/schema.py`: frozen `SourcePointer` + `Fact` (Decimal only, 3 locator forms, lineage/month checks); `to_json` (value as string) / `from_json` re-runs all checks. `tests/test_fact_schema.py`: 23 tests incl. planted errors. Next: C1.2 (database).

## 2026-10-29 — T-006 done
- `docs/requirements.md`: 19 requirements (UR-01..19) and 14 risks (RK-01..14, each with control + test or `future:` chunk, covering every UR). `tests/test_requirements.py`: 7 tests incl. 5 planted-error ones.
- Old stash dropped (only held the attribution setting, already committed). `tests_live` 7 OK after restarting docker (Neo4j needs ~1 min to become healthy).

## 2026-10-28 — T-001 done
- Git started: commit 1 = baseline (old work unchanged), commit 2 = `ectd_engine/` skeleton (facts, writer, validator, ledger) + `tests/test_smoke.py`.
- Watch tool verified: touching a frozen file (`writer_test/README.md`) is flagged. Next: T-002.

## 2026-10-28 — migration to brain/hands model
- Handoff folder created: `E:\E\Project\handoff\` (brain files, archive, tools).
- Repo not bootstrapped yet. Next task: T-001 (see handoff/brain/04_plan_and_next_steps.md). Master plan drafted (phases 0–7, ~42 sessions); the new project's first chat reviews it.
- Watch tool installed: tools/watch.py + hooks in .claude/settings.json (log to .brain/activity.log).
- Writer harness (`writer_test/`): 43 unit tests pass; mock run 8/8; mutation test all planted errors caught; audit round 2: 116 accepted, 0 wrong, 4 misleading (fixed after), 20 awkward.
- Pending, needs Hil on laptop: round-3 audit `python -m writer_test.run --model gemma4:e4b --audit 20` (close Excel first); report counts ok/awkward/misleading/wrong.
- Open decisions for Hil: O1 SQLite vs Postgres for M1–M3; O2 repo layout; O3 next Module-3 sections (see brain/02_decisions_log.md).
- Known limits: stability paragraphs only, one model; synthetic data; OCR check only simulated.
- K1 done: context gauge 68.8k/1m (7%); biggest: messages 26.4k, MCP 13.1k, skills 9.8k (see learn/LEARN_K1.md).
- K2 done: status line (tools/statusline.py) shows task id | ctx % | cost | 5h %; 60 tests pass; restart Claude Code to see it.

## 2026-10-29 — K3 done
- Guard hook: `python tools/watch.py guard` (PreToolUse on Edit|Write|MultiEdit|NotebookEdit) exits 2 for a frozen path the task does not allow; 9 tests in tests/test_guard.py. Bash writes are NOT covered. Backup: .claude/settings.backup.json (untracked). Restart Claude Code to load the hook.
- Known: tests/test_gate.py fails (19 errors + 1 failure) since commit 6678280 "second entry of ranges": ranges.json and ranges_check.json disagree. Not touched by K3; needs a card.

## 2026-10-29 — T-015 done
- Lek loader `python -m ectd_engine.loaders.lek --dry-run` -> accepted 4965, quarantined 60 (20 batches; part > total, reason code CROSS_FIELD). Dry run only; no live load. ranges.json/units.json now cover Impurity O/L, Total impurities, Residual solvent (match ranges_check.json, so test_gate is green again). 8 tests in tests/test_lek.py. Locator row=N is the spreadsheet row (header = row 1).

## 2026-10-30 — T-020 done
- Stats 1: `ectd_engine/stats/basic.py` (mean, sd n-1, rsd_percent, round_to half-up, conforms rounds to each limit's own decimals first). Decimal only, prec 50. 6 tests in tests/test_stats_basic.py; 5 NIST StRD files in data/public/nist/ (certified values parsed from headers) all match to 15 digits. Full suite 173 OK.

## 2026-10-30 — K4 done
- Output style `Plain words` (`.claude/output-styles/plain-words.md`, 5 rules, keep-coding-instructions true) set via `"outputStyle": "Plain words"` in `.claude/settings.json` (exact case; hooks, deny list, attribution untouched). 7 tests in `tests/test_output_style.py`. Restart Claude Code, then `/output-style`.

## 2026-10-30 — T-022 done
- `ectd_engine/stats/pool.py`: `poolability(batches, spec_min, spec_max)` -> decision ("separate" / "common slope, separate intercepts" / "fully pooled"), `p_slope`, `p_intercept`, shelf life (separate = shortest batch; common slope = pooled error, df N-k-1, own intercepts; pooled = `shelf_life` on all points). `decide()` pools only if p > 0.25. `tdist.f_cdf` added (general incomplete beta). q1e.py unchanged (only called; `_one_side` reused).
- 12 tests in `tests/test_pool.py`; p-values match statsmodels anova_lm to 10 digits (cases a/b/c).

## 2026-10-30 — T-021 done
- `ectd_engine/stats/tdist.py`: Student t cdf/quantile in Decimal (incomplete beta, bisection; checked vs t-table and scipy). `q1e.py`: `fit`, `Fit.bound(month, side)` (one-sided 95% bound of the mean line), `shelf_life(points, spec_min, spec_max, cap_months)` solved to 0.01 month (half-up), cap = min(2 x longest, longest + 12) with `capped` + reason; `line_shelf_life` is the wrong-way comparator for tests only.
- Matches statsmodels to 10 digits (slope, intercept, bound); shelf life within 0.01 month. `requirements-dev.txt` pins statsmodels 0.15.0 + scipy 1.13.1 (test-only). Poolability stays C1.11.

## 2026-10-30 — K5 done
- `/where`, `/explain`, `/recap` moved to `.claude/skills/<name>/SKILL.md` (text unchanged, disable-model-invocation true); new `/verify` (allowed-tools only `Bash(python tools/watch.py *)`) runs `watch.py status --tests`. `.claude/commands/` removed. 8 tests in `tests/test_skills.py`. Restart Claude Code to see the 4 skills.

## 2026-10-30 — T-023 done
- `ectd_engine/stats/oot.py`: `check(history, (month, value), level=0.99)` -> OK | OOT (with low/high) | NotEnoughData (< 3 points or all same month); uses the two-sided PREDICTION interval (`interval`). `check_with_policy` returns (result, note).
- `ectd_engine/stats/loq.py`: `parse` ("<LOQ", "<0.05", "ND" -> Below), `Policy` EXCLUDE (default) / REPORT_ONLY / SUBSTITUTE (needs value + reason, else ValueError), `apply_policy`, `shelf_life_with_policy` -> (ShelfLife or None, note). 22 tests in `tests/test_oot_loq.py`; PI matches statsmodels to 10 digits. q1e.py/tdist.py unchanged. Suite 226 OK.

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
