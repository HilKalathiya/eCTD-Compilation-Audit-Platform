# 06 File map

## On Hil's PC (`E:\E\Project\`)
| Path | What | Open it? |
|---|---|---|
| `handoff\` | THIS migration folder | start at `00_READ_FIRST.md` |
| `handoff\brain\` | small brain files (01–08 + STATE.md) = what the Claude Project loads (`08` = Claude Code mastery track) | yes |
| `handoff\archive\` | explainer_full.md (216 KB), technical_brief.md, problems_and_solutions.md, model_choice_and_costs.md, old overview docs | NO. Use `python tools/section.py <doc> <n>` |
| `tools\` (root; copy in `handoff\tools\`) | `watch.py` (brain's eyes: status, run, task, hook log), `section.py` (print one explainer section), `estimate_tokens.py` | run |
| `.claude\settings.json` | deny-list for big files + hooks that log Claude Code's actions to `.brain\activity.log` | do not edit |
| `.brain\` | `activity.log`, `task.json` written by hooks/watch.py (not in git) | brain reads via `watch.py status` |
| `.claude\commands\` | `/explain`, `/where`, `/recap` (teaching commands for Hil) | type in Claude Code |
| `learn\` | `LEARN_<task>.md` after each task + `GLOSSARY.md` (plain-words notes for Hil) | Hil reads |
| `CLAUDE.md`, `STATE.md` (root) | hands' rules; current status | yes |
| `writer_test\` | frozen baseline: stability-paragraph writer harness (facts.py, validator.py, rendercheck.py, mutation_test.py, prompt.py, llm.py, run.py, compare.py, tests/, data/tasks.json, README.md) | run commands in CLAUDE.md |
| `writer_test\outputs\ollama_gemma4-e4b\` | audit_labelled.csv (round 1), audit2_labelled.csv (round 2), audit_20261028_084851.csv/.jsonl, summary.md, blind_ratings.csv, reference\ (5 Claude paragraphs) | evidence only |
| `checks_stress_test\` | tracing.py, s2_number_words.py, s3_rederive.py, README.md, results json | evidence only |
| `ocr_stress_test\` | sim.py, run.py, analyze.py, make_doc.py, README, results.json | evidence only |
| `Laboratory.csv` | Lek/Sandoz 1,005-batch dataset (CC BY 4.0), do not alter | head/grep only |
| `Claude outputs\` | FDA Kerendia label PDF (215341Orig1s009lbl.pdf), `eCTD model choice and costs.md`, finerenone_ocsr_check.py, finerenone.png, swin_base_char_aux_1m.pth (large) | no |
| `AI Evidence Engine ... Technical Brief.docx/.md`, `CMC Compilation & Audit Engine — Complete Explainer.pdf` | older exports (the .md here is older than archive/technical_brief.md) | no |
| `Life Sciences & Pharmaceutical R&D\` | OLD blueprint: overview_discription.md, detailed_overview.md (Claude Opus 4.6, DeepSeek-R1, Neo4j Aura, Pinecone, GovCloud). OUTDATED and contradicts the design | never load |

## Living documents (Claude Docs, claude.ai)
- Explainer (38 sections): https://claude.ai/artifact/KBj4ZNfYk6L79ZgBqA8fcS (id 9343dad4-95e5-4ce7-a3e5-7274f3eb1e07)
- Problems and Solutions (3 tables): https://claude.ai/artifact/FGYdbJUgUzuutATQszuY8g
- Technical Brief (for his brother): https://claude.ai/artifact/8zxgdVyPfqJG36qZBg9KmV

## Explainer section index (use `python tools/section.py explainer <n>`)
1 one page · 6 facts-first · 7 numbers to claims · 8 evidence graph · 12 parsing/OCR+VLM · 13 knowledge layer · 14 orchestration · 15 models · 16 math sandbox · 17 review UI · 18 ledger/Part 11 · 19 security · 20 impurity walkthrough · 21–26 other modules · 28 latest tech · 30 challenges + independence audit · 31 roadmap · 33 vs Weave · 34 UX · 35 scorecard · 36 student build + real data · 37 glossary · 38 sources.

## Claude Project memory (account level)
Goals, laptop constraints and preferences are stored in Claude memory; the brain files here are authoritative for the build.
