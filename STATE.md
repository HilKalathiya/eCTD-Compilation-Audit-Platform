# STATE (newest first; Claude Code keeps this <= 40 lines; Hil re-uploads it to the Claude Project after each milestone)

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
