# STATE (newest first; Claude Code keeps this <= 40 lines; Hil re-uploads it to the Claude Project after each milestone)

## 2026-10-28 — migration to brain/hands model
- Handoff folder created: `E:\E\Project\handoff\` (brain files, archive, tools).
- Repo not bootstrapped yet. Next task: T-001 (see handoff/brain/04_plan_and_next_steps.md). Master plan drafted (phases 0–7, ~42 sessions); the new project's first chat reviews it.
- Watch tool installed: tools/watch.py + hooks in .claude/settings.json (log to .brain/activity.log).
- Writer harness (`writer_test/`): 43 unit tests pass; mock run 8/8; mutation test all planted errors caught; audit round 2: 116 accepted, 0 wrong, 4 misleading (fixed after), 20 awkward.
- Pending, needs Hil on laptop: round-3 audit `python -m writer_test.run --model gemma4:e4b --audit 20` (close Excel first); report counts ok/awkward/misleading/wrong.
- Open decisions for Hil: O1 SQLite vs Postgres for M1–M3; O2 repo layout; O3 next Module-3 sections (see brain/02_decisions_log.md).
- Known limits: stability paragraphs only, one model; synthetic data; OCR check only simulated.
