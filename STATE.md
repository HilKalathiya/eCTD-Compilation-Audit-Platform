# STATE (newest first; Claude Code keeps this <= 40 lines; Hil re-uploads it to the Claude Project after each milestone)

## 2026-10-29 — T-008 done
- Fact box tightened: batch/condition non-empty ("n/a" allowed), value text must be plain `-?\d+(\.\d+)?`, unknown JSON keys refused. 56 tests.
- Round-3 audit: 160 drafts, 49 rejected, 111 accepted: 92 ok / 19 awkward / 0 misleading / 0 wrong. The one "out of specification" note (acc_impurity_b_oos draft 13): B3 Month 6 = 0.18 > NMT 0.15, so facts say fails -> row is awkward, not wrong.

## 2026-10-29 — T-007 done
- `ectd_engine/facts/schema.py`: frozen `SourcePointer` + `Fact` (Decimal only, 3 locator forms, lineage/month checks); `to_json` (value as string) / `from_json` re-runs all checks. `tests/test_fact_schema.py`: 23 tests incl. planted errors. Next: C1.2 (database).

## 2026-10-29 — T-006 done
- `docs/requirements.md`: 19 requirements (UR-01..19) and 14 risks (RK-01..14, each with control + test or `future:` chunk, covering every UR). `tests/test_requirements.py`: 7 tests incl. 5 planted-error ones.
- Old stash dropped (only held the attribution setting, already committed). `tests_live` 7 OK after restarting docker (Neo4j needs ~1 min to become healthy).

## 2026-10-29 — T-005 done
- `docker compose --profile db --profile graph up -d` starts Postgres 16 + pgvector (5432) and Neo4j 5.26 (7474/7687); passwords in git-ignored `.env` (template `.env.example`).
- `ectd_engine/db/`: `postgres.float_columns`, `graph.check_props`; `tests_live/` 7 live tests (Decimal 0.140 exact in NUMERIC and Neo4j string, pgvector, planted float alarms). psycopg 3.3.6, neo4j 6.4.1 pinned.

## 2026-10-29 — T-004 done
- Claude co-author lines removed from all commits (history rewritten, backup `../ectd_backup_before_rewrite.bundle`); `.claude/settings.json` now sets attribution empty. Force-pushed.
- CLAUDE.md rule 8 now: commit without AI attribution, `git push origin main`, never force-push; REPORT has a `Pushed:` line.

## 2026-10-28 — T-003 done
- `tests/test_watch.py`: 13 tests; all 11 watch.py flags have planted tests (added: assertions weakened, requirements.txt changed, large file). watch.py untouched.

## 2026-10-28 — T-002 done
- `tests/test_watch.py`: 9 tests; all 8 watch.py flags fire on planted mistakes and a clean change gives `FLAGS: none`. watch.py untouched.

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
