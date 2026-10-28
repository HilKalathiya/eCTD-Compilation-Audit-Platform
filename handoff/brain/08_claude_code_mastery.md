# 08 Claude Code mastery (Track K): Hil wants to customise Claude Code like an expert developer

## Goal and limits
Hil wants real control of Claude Code: settings, hooks, skills, subagents, output styles, status line, MCP, token tuning. It is a skill he keeps for life and a portfolio talking point (a `.claude/` toolchain in the repo plus a README section).
Be blunt about the cost: this is a side-quest. Cap: 10 cards, each <= 30 min, about 10% of all sessions. A K card never delays a checkpoint (A0, A, B, C0, C, D). If the schedule slips, drop K cards in this order: K10, K9, K8, K7, K5. Never drop K1-K4 or K6.

## How a K card works
- It is a normal TASK CARD, chunk id `K<n>`, with two extra lines: `WHY EXPERTS DO THIS` (1 line) and `YOU TRY` (a 5-minute change Hil makes himself and sees the effect).
- `.claude/` and `tools/watch.py` are frozen by default. Step 1 of the card must name them in the `watch.py task` globs (e.g. `".claude/**"`, plus `"tools/**"` when a script changes).
- Before writing a K card, check the current docs page (map below). Claude Code changes fast; never write settings or hook fields from memory.
- Every `settings.json` edit: keep the existing `PostToolUse` and `Stop` log hooks and the deny-list; copy the file to `settings.backup.json` first; validate with `python -c "import json;json.load(open('.claude/settings.json'))"`. One stray comma breaks every hook.
- Hooks and status-line scripts: stdlib Python, no network, under 1 second. A hook is code that runs on every action.
- Every guard or hook gets a planted-error test: feed it fake stdin JSON and assert the exit code (same independence rule as the engine).

## The ladder (issue in this order; the brain may move a card with a one-line reason)
| K | When | Build | Why experts do this | Done when |
|---|---|---|---|---|
| K1 | after C0.1 | No code. Run `/context`, `/usage`, `/memory`, `/doctor`, `/mcp`; read what fills the window | Context is a fuel gauge; waste is invisible until measured | Hil names the 3 biggest items and one way to shrink each |
| K2 | after C1.1 | Status line: Python script reading stdin JSON; shows task id (from `.brain/task.json`), context %, session cost, 5-hour limit % | Live gauges; plan limits are Hil's real budget | All four show. `rate_limits` is absent until the first reply: script must not crash |
| K3 | after C1.3 | PreToolUse guard hook: exit 2 when Edit/Write targets a frozen path outside the task globs (add a `check` command to `tools/watch.py`, hook calls it) | Hooks enforce; CLAUDE.md only asks | Fake input for `writer_test/x.py` -> exit 2; allowed path -> exit 0 |
| K4 | after C1.5 | Output style: try built-in Explanatory and Learning, then a custom `.claude/output-styles/plain-words.md` (`keep-coding-instructions: true`, under 15 lines) | A style sets tone without bloating CLAUDE.md; it is paid for on every turn, so keep it tiny | `outputStyle` set; replies teach in plain words |
| K5 | after C1.9 | Commands -> skills: move `/where`, `/explain`, `/recap` to `.claude/skills/<name>/SKILL.md`; add `/verify` (runs `watch.py status --tests`); `disable-model-invocation: true` | A skill costs only its description until used | 4 skills work; old `.claude/commands/` removed after checking |
| K6 | after C2.1 | Path-scoped rules: engine-only rules (Decimal, no `float`/`round`, fact-store API) into `.claude/rules/engine.md` with `paths: ectd_engine/**`; CLAUDE.md under 200 lines | Rules load only when relevant: cheaper every turn | `/memory` shows the rule only when an engine file is open |
| K7 | after C2.2 | Subagent `test-runner` (`model: haiku`, tools limited to Bash/Read): runs tests, returns <= 10 lines | Heavy output stays out of the main context; a cheap model does chores | Main session gets 10 lines instead of hundreds; `/context` before/after |
| K8 | with C5.2 | MCP: connect one existing server and watch its context cost; then our own read-only fact-store server (this is C5.2) | The extension point experts use; ties to the portfolio | `claude mcp list` shows ours; a query returns a fact with its source |
| K9 | after C3.7 | Headless: `claude -p "<tiny prompt>"` in a script that runs the ACCEPT checks. Check the docs whether GitHub Actions can use the plan login; if it needs an API key, skip Actions (no API budget) | Automation without a person at the keyboard | Script prints PASS/FAIL. Headless runs count against plan limits |
| K10 | after C7.4 | Package K2-K7 as a plugin in a small marketplace repo; README section "My Claude Code toolchain" | Plugins are how teams share setups | Installs from the local folder on a clean clone |
Later, only after K10: git worktrees, parallel sessions, dynamic workflows.

## Verified facts (Oct 2026, code.claude.com docs)
- Hooks: handler `{type:"command", command, args[], timeout}`; `${CLAUDE_PROJECT_DIR}`; stdin JSON has `tool_name`, `tool_input`, `cwd`; exit 2 blocks, other non-zero does not; PreToolUse can block or rewrite (`updatedInput`); PostToolUse takes `matcher`, Stop has none.
- Memory: keep CLAUDE.md under 200 lines; `.claude/rules/*.md` with `paths` frontmatter loads only for matching files.
- Skills: `.claude/skills/<name>/SKILL.md`; legacy `.claude/commands/*.md` still works; `$ARGUMENTS`; `disable-model-invocation: true`. Subagents accept `model: haiku` and a `skills:` list.
- Output styles: built-in Default, Proactive, Concise, Explanatory, Learning; custom files in `.claude/output-styles/`; the `outputStyle` value is case-sensitive.
- Status line: `statusLine: {type:"command", command, padding}`, optional `refreshInterval` (min 1 s). Stdin JSON includes `model.display_name`, `workspace.current_dir`, `context_window.used_percentage`, `cost.total_cost_usd`, `rate_limits.five_hour.used_percentage` (Pro/Max only, may be absent). Python works on Windows (no `jq` needed). `/statusline <plain-English request>` generates one.
- Tokens: `/context`, `/usage`, `/clear`, `/compact <focus>`, `/model`, `/effort`, plan mode (Shift+Tab), `/rewind`. Guardrails belong in hooks, not CLAUDE.md.

## Doc map (base `https://code.claude.com/docs/en/`)
Read this session: `features-overview` (which feature for which need), `hooks`, `costs`, `output-styles`, `statusline`.
Slugs not yet read (search the docs index if one 404s): `settings`, `memory`, `skills`, `sub-agents`, `mcp`, `plugins`, `headless`, `agent-sdk`, `model-config`.
