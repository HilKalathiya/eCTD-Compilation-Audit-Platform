# 04 MASTER PLAN (chronological; the brain owns it and may re-order with a one-line reason)

Unit: 1 session = 1–2 h of Hil + Claude Code. Effort numbers are rough guesses, not measurements (~42 sessions, ~9–10 weeks at 4–5 sessions/week). Task cards are numbered T-001, T-002 … in order issued; each card names its chunk (e.g. "T-004 / C1.2").

## Ordering rules
1. No-model work first (deterministic, testable, fast), model work second, UI third, scans/orchestration after.
2. Every chunk ends with something runnable AND a planted-error test proving its check can fail (independence rule).
3. Four demo checkpoints (A–D) so something is showable early for the job search.
4. If a checkpoint fails, stop and replan; do not start the next phase.

## Phase 0 — Setup (1 session)
| C | What | Done when |
|---|---|---|
| C0.1 | Repo bootstrap (card T-001 below): `ectd_engine/` skeleton, tests/, git, `.gitignore`, watch tool check | smoke test passes; `python tools/watch.py status` works |
| C0.2 | (Hil, any time) Round-3 audit of the writer: `python -m writer_test.run --model gemma4:e4b --audit 20` | counts ok/awkward/misleading/wrong in STATE.md; if any "wrong" -> add check first |

## Phase 1 — Data spine, no model (9 sessions)
| C | What | Done when |
|---|---|---|
| C1.1 | Fact schema: id, value (Decimal), unit, batch, test, condition, month, source pointer, lineage, definition | schema tests; round-trips to JSON |
| C1.2 | Write gate + quarantine: schema contract, unit rule table, plausible ranges, agreement only from independent routes (copies never count; unknown lineage = copy) | bad rows land in quarantine with a reason |
| C1.3 | Planted-error tests for the gate: wrong batch, decimal shift (0.14 vs 0.014), copy as 2nd source, unit swap | all caught; 0 good rows rejected |
| C1.4 | Lek loader: `Laboratory.csv` (semicolon, typo column `resodual_solvent`) -> facts; quarantine the 20 batches where impurity > total | fact counts match CSV; 20 quarantined with reason |
| C1.5 | Kerendia facts hand-entered from FDA review + label with page cites (10/20 mg review vs 40 mg label = version conflict) | conflict stored as two sourced facts, flagged |
| C1.6 | Stats library part 1: mean/SD/%RSD, spec comparison, Decimal ROUND_HALF_UP to spec decimals | `round(0.125,2)` trap test passes |
| C1.7 | Stats part 2: ICH Q1E regression, poolability at 0.25, one-sided 95% bound shelf life, extrapolation limit | matches statsmodels on synthetic series |
| C1.8 | Stats part 3: OOT prediction interval, `<LOQ` policy | edge cases tested (missing points, ties, <LOQ) |
| C1.9 | Validate stats against NIST StRD certified values (+ R if installed) | agreement to documented digits |
**Checkpoint A0:** `python -m ectd_engine.demo_facts` loads Lek, prints a fact with its source row, shows a planted bad row quarantined.

## Phase 2 — Writer on the fact store (6 sessions)
| C | What | Done when |
|---|---|---|
| C2.1 | Port `writer_test` facts/validator/rendercheck onto the fact store (keep `writer_test/` frozen) | 43 ported tests + mutation test pass |
| C2.2 | LLM client in engine (Ollama / OpenAI-compatible / mock); run the 8 tasks | mock 8/8; Gemma 4 E4B run on laptop |
| C2.3 | Fresh audit (round 3) on the engine; close gaps by planted-error tests | >=100 accepted, 0 wrong |
| C2.4 | New section type: 3.2.P.5.4 batch analyses on Lek data (table + paragraph), own word lists + mutation kinds | mutation test 100% caught, 0 false rejects; audit as above |
| C2.5 | New section type: 3.2.P.5.1/5.6 specifications + justification (limits from spec facts only; retrieval quotes only) | same bar |
| C2.6 | Code-owned content plan + render to .docx/HTML | every required fact appears or draft rejected |
**Checkpoint A (resume-ready CLI demo):** CSV -> facts -> stats -> drafted section by Gemma on the laptop -> validator -> rendered doc; plant one wrong number -> rejected. Record a 2-minute video.

## Phase 3 — Trust layer + UI (7 sessions)
| C | What | Done when |
|---|---|---|
| C3.1 | Ledger: SHA-256 hash chain, append-only API, external anchor file, verify script | any manual row edit makes `verify` exit non-zero |
| C3.2 | Wire ledger to gate, writer (model id, prompt hash), validator verdicts, human actions | one section run produces a verifiable chain |
| C3.3 | Review backend (FastAPI): sections, facts, sources, verdicts, e-signature record (name, time, meaning) | API tests pass |
| C3.4 | UI shell (React): dossier tree, section workspace (serif canvas), fact chips with states | page renders a drafted section |
| C3.5 | Click chip -> source panel (CSV row; PDF page box via PDF.js) | every number opens its source |
| C3.6 | Review-by-exception queue + blind entry for high-risk values + challenge items | reviewer sees only flagged items |
| C3.7 | Sign-off blocked while any check fails; signed export; ledger entry | blocked/allowed cases tested |
**Checkpoint B (portfolio demo):** in the browser, click a number -> source; failed check blocks signing; tampering breaks `verify`.

## Phase 4 — Scans (5 sessions)
C4.1 render Lek values as synthetic CoA scans at 4 qualities (reuse `ocr_stress_test/`) · C4.2 reader 1: layout OCR with cell coordinates (Docling/Tesseract/PaddleOCR) · C4.3 reader 2: blind VLM read (Gemma 4 / free tier, public scans only) · C4.4 cross-check into the write gate: grid binding + header check, typed parse, rules, zoom re-read, independent families · C4.5 measure: 0 wrong auto-accepted over >=5,000 values, report % sent to a person; try a handful of real CoAs by hand. **Checkpoint C0:** measured table in the repo.

## Phase 5 — Orchestration and connectors (4 sessions)
C5.1 LangGraph section pipeline with checkpointer · C5.2 two read-only MCP servers (LIMS over CSV, document store) · C5.3 resume-after-kill test; failed verification = non-retryable -> human queue · C5.4 Temporal wrap of one workflow with one durable human wait (cut first if time is short).

## Phase 6 — Whole-dossier consistency demo (5 sessions)
C6.1 evidence graph tables: facts, claims, placements, derivations · C6.2 every rendered number records its placement; change propagation lists affected placements and flags prose · C6.3 Kerendia audit (FDA review vs 2025 label, 40 mg difference found and linked to both sources) · C6.4 CDISC Pilot 01: SDTM re-derivation vs CSR numbers (reuse `checks_stress_test/s3_rederive.py`); ADaM copy never counts as independent · C6.5 demo script: plant one wrong number in a copy -> detected, placements listed, prose flagged. **Checkpoint C.**

## Phase 7 — Evaluation and polish (5 sessions)
C7.1 seeded-error study with errors from outside the team (openFDA CRL deficiencies, OCR misreads, a classmate) · C7.2 GEPA prompt tuning judged on held-out checks (optional) · C7.3 QLoRA of Gemma 4 only if pass rate is low (optional) · C7.4 README, architecture diagram, evaluation report with honest limits, demo video, clean GitHub repo · C7.5 resume bullets + portfolio-site entry. **Checkpoint D.**

## Track K — Claude Code mastery (Hil's own goal; details in `brain/08_claude_code_mastery.md`)
10 small cards K1-K10 (<= 30 min each, about 10% of sessions) interleaved with the phases: K1 after C0.1 · K2 after C1.1 · K3 after C1.3 · K4 after C1.5 · K5 after C1.9 · K6 after C2.1 · K7 after C2.2 · K8 with C5.2 · K9 after C3.7 · K10 after C7.4. Order: gauges and guards first, extensions last.
Rules: a K card never delays a checkpoint; it carries `WHY EXPERTS DO THIS` and `YOU TRY` lines; its `watch.py task` globs must include `.claude/**` (frozen otherwise); the brain reads the current docs page before writing it.

## If time runs out (cut in this order)
Temporal wrap -> GEPA -> QLoRA -> Neo4j (use SQLite tables) -> real CoAs -> Phase 6.5 -> K10, K9, K8, K7, K5. Never cut: planted-error tests, round-3 audit, the evaluation report, K1-K4, K6.

## Open decisions (brain recommends, Hil confirms in chat 1)
O1 fact store: SQLite for Phases 1–4, Postgres at C5.1? [recommend yes] · O2 `ectd_engine/` new package, `writer_test/` frozen [recommend yes] · O3 UI: React + FastAPI [recommend yes].

## First card (T-001 / C0.1)
```
TASK T-001 (C0.1): Bootstrap repo                MODEL: sonnet
GOAL: Create the engine skeleton without touching existing experiment folders.
WHY: A clean folder and version history first, so every later piece of code has a home and every change can be undone.
READ ONLY: CLAUDE.md, STATE.md
CHANGE: ectd_engine/**, tests/**, requirements.txt, .gitignore, STATE.md
DO: 1 `python tools/watch.py task T-001 "ectd_engine/**" "tests/**" "requirements.txt" ".gitignore" "learn/**"`
    2 create ectd_engine/{__init__.py,facts/,writer/,validator/,ledger/} (each with __init__.py) and tests/test_smoke.py importing ectd_engine
    3 .gitignore: .brain/, __pycache__/, *.pyc, outputs/, audit_*.csv, *.pth, *.pdf, Laboratory.csv
    4 write learn/LEARN_T-001.md and learn/GLOSSARY.md (teaching rules in CLAUDE.md)
    5 empty requirements.txt; git init; commit "bootstrap" (writer_test/ etc. committed as-is; do not edit them)
ACCEPT: `python -m unittest discover tests` -> OK (1 test); `python tools/watch.py status` -> FLAGS: none; `git log --oneline` -> 1 commit
DON'T: modify writer_test/, checks_stress_test/, ocr_stress_test/, tools/watch.py, .claude/; add dependencies
REPORT: standard
```
