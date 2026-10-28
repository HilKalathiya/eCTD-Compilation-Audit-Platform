# 02 Decisions log (settled unless marked OPEN; do not re-open without new evidence)

| # | Decision | Why / evidence |
|---|---|---|
| D1 | Scope = whole eCTD (M1–M5); Module 3 built first (2026-10-14, Hil) | CMC is the most number-heavy, easiest proof; same engine extends |
| D2 | Model never writes a number; facts-first + validator + code render | "usually right" can't be validated; makes AI a unit-testable software problem |
| D3 | Evidence graph + cross-module consistency engine is the product edge; evidence-first vs Weave's drafting-first | Weave's own AutoIND study: quality 69.6%/77.9%, 10–25% content needed revision, wrong values/NOAELs |
| D4 | Temporal outside + LangGraph 1.2.x inside; Postgres checkpointer; ledger (not Temporal history) is the GxP record. Student build: LangGraph first, wrap in Temporal at first human wait | sign-offs wait days; failed verification = non-retryable -> person, never retry-until-pass |
| D5 | Graph primary at v1 + PostgreSQL backup filled from same write gate | lineage/impact queries; no drift. Student: Postgres+pgvector+FTS, Neo4j Community |
| D6 | Validated stats library as tools over fact IDs; "PyChain WASM" removed; free code only in Firecracker microVM, non-GMP | model-typed values were a high-severity flaw in the old overview |
| D7 | Rounding with Decimal ROUND_HALF_UP to spec decimals | Python round(0.125,2)=0.12 is a silent bug |
| D8 | Production models: Opus 5.5 draft/GEPA, Textract + Gemini 3.8 Flash scan readers, Haiku 5.5 routing, local hybrid retriever; EU Claude via Bedrock eu. profiles; Anthropic API has no EU-only option | research report 2026-10-26 (archive/model_choice_and_costs.md); self-host loses on cost until ~150–240 dossiers/month |
| D9 | $0 student build: Gemma 4 E4B laptop, Gemma 4 26B Kaggle, no paid API | Hil's budget; harness proves it works on an easy templated task |
| D10 | Scan check: blind reads, grid binding + header check, column-aware typed parse, rules, zoom re-read, independent model families (not Paddle+GLM) | first OCR+VLM check was circular (VLM repeats OCR) |
| D11 | MolScribe (OCSR) dropped; scanned structure drawings go to a person; RDKit checks registry structures | failed on finerenone label |
| D12 | Independence rule: a check counts only if it can fail | 10 flaws found in own design (explainer §30) |
| D13 | Wrong-binding design = compound facts + closed vocabulary + code-owned trend/compliance/required facts + re-read; entailment = reviewer flag only; grammar decoding only if too many rejects | research on 6 approaches (explainer §30/§15) |
| D14 | Real public data only; anchor drug Kerendia (finerenone, NDA 215341); Lek/Sandoz batches; CDISC Pilot 01; openFDA CRLs | no public real stability time series exists -> stats validated vs R/NIST |
| D15 | Retrieval only QUOTES guidelines; spec limits come from spec facts, thresholds from a versioned rule table (entered twice, tested on guideline examples) | limits-by-retrieval was a flagged flaw |
| D16 | Reviewer: blind entry for high-risk values + per-reviewer challenge items | reviewer shown the answer first just agrees |
| D17 | GEPA for prompts only, offline, judged on held-out checks + human golden set; no RL fine-tuning; LoRA/QLoRA only if pass rate is low | weights change = re-validation |
| D18 | Operating model (2026-10-28): Claude Project = brain (decides, plans, writes TASK CARDS, judges REPORTS); Claude Code terminal = hands (all code) | Hil's rule; keeps tokens low |
| D19 | UI: Weave-inspired but evidence-first; FastAPI + React + PDF.js + Tiptap with fact chips | explainer §34, brief §9 |

## OPEN (need Hil's OK; brain's recommendation in brackets)
- O1 Fact store for M1–M3 on the laptop: SQLite now, Postgres at M8? [SQLite: less disk/RAM; hash-chain and write gate don't need Postgres]
- O2 Repo layout: new package `ectd_engine/`, `writer_test/` frozen as baseline? [yes]
- O3 Next Module-3 sections after stability: 3.2.P.5.1 specs and 3.2.P.5.4 batch analyses? [yes, Lek data exists for 5.4]
- O4 Harder Module 2 summary test of Gemma vs Claude (Hil declined for now)
- O5 Third audit of the writer (fresh test; pending)
