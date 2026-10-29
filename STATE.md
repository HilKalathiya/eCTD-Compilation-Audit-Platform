# STATE (newest first; Claude Code keeps this <= 40 lines; Hil re-uploads it to the Claude Project after each milestone)

## 2026-10-29 — T-004 done
- Claude co-author lines removed from all commits (history rewritten, backup `../ectd_backup_before_rewrite.bundle`); `.claude/settings.json` now sets attribution empty. Force-pushed.

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
