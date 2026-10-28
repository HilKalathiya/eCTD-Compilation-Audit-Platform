# READ FIRST — migration to the new Claude Project (brain) + Claude Code (hands)

Everything done so far is in this folder. Nothing is lost; the heavy material is in `archive\` and is never loaded unless needed.

## Do this once (about 5 minutes)
1. **New Claude Project, Instructions box:** open `PROJECT_INSTRUCTIONS.md`, copy all, paste.
2. **New Claude Project, Knowledge:** upload ONLY these 9 files: everything in `brain\` (01–08) plus `STATE.md`. About 9,500 tokens in total. Do NOT upload `archive\`. If the old docs `overview_discription.md` / `detailed_overview.md` are in that project, remove them: they are outdated and contradict the design.
3. **Claude Code:** already set up for you in `E:\E\Project\`: `CLAUDE.md`, `STATE.md`, `tools\` (incl. `watch.py`) and `.claude\settings.json` (hooks that log what Claude Code does, plus a deny-list for big files). Open a terminal there and run `claude`.
4. **First chat:** open `FIRST_CHAT.md` and paste Message 1 (the planner), then Message 2 (how the brain watches Claude Code). Message 0 (explainer read-through) is optional.

## To follow along (you are not expected to read code)
- Second terminal: `python tools/watch.py live` shows what Claude Code is doing, in plain English.
- In Claude Code type `/where` (6 lines: what now), `/explain` (what it just did and why), `/recap` (everything so far).
- After every task read `learn\LEARN_<task>.md` (15 lines: what was built, why this way, one command to try).

## Then, every day
New chat in the project, say: **"next"**. The brain gives you one TASK CARD. Paste it into Claude Code. Paste Claude Code's REPORT back into the project chat. Repeat. The brain checks Claude Code with `tools\watch.py` (it logs every edit and command through hooks; flags out-of-scope edits, deleted tests, new skips, `round()`/`float()` in engine code, new dependencies).

## What is where
- `PROJECT_INSTRUCTIONS.md` — brain's role + loop + token rules
- `CLAUDE.md` — hands' rules + commands that work
- `STATE.md` — one-page current status (keep updated)
- `FIRST_CHAT.md` — exact messages to paste, in order
- `tools\watch.py` — brain's eyes on Claude Code; for you: `python tools/watch.py live` (plain-English live feed)
- `brain\01..08` — design, decisions, results, plan, you, file map, history, Claude Code mastery track
- `archive\` — full explainer (216 KB), technical brief, problems and solutions, model/cost report. Read a section with `python tools/section.py explainer 13`
- `tools\` — section.py, estimate_tokens.py

## Honest status
Done and tested: the $0 writer harness (Gemma 4 on your laptop), planted-error tests, stress tests on real data, OCR check (simulated). Not built yet: the engine itself (fact store, stats library, ledger, UI). Round-3 audit still to run.
