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
