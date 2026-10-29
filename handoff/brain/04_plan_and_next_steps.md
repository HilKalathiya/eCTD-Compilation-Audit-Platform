# 04 MASTER PLAN v2 (2026-10-28; nothing from the explainer is cut)

Source of scope: `archive/explainer_full.md` (§36 student build and whole-eCTD version, §28 additions, §31 roadmap, §34 product, §13 knowledge layer).
Rule from Hil (2026-10-28): **no scope cuts.** If the schedule slips, the timeline gets longer; nothing is dropped and the order stays.
Unit: 1 session = 1-2 h of Hil + Claude Code. ~100 sessions (rough guess, not measured): ~5 months at 4-5 sessions/week.
Every chunk: <= 2 sessions, ends runnable, and ships a planted-error test that proves its check can FAIL (independence rule).
Cards are numbered T-001, T-002 ... in issue order; each names its chunk. Git branch: `master`.

## Ordering rules
1. No-model work first, model work second, UI third, scans/orchestration after; the evidence graph is built from Phase 1 on (explainer §31).
2. Checkpoints (A0, A, B, C, E, D0, F, D) give something showable early. A failed checkpoint = stop and replan.
3. Errors from outside the team (classmate, CRL deficiencies, OCR misreads) at every checkpoint from A on, not only at the end.
4. Heavy services (Postgres, Neo4j, Langfuse, Ollama) run through `docker compose` profiles, only the ones a task needs (16 GB RAM).

## Phase 0 - Setup
| C | What | Done when / planted error |
|---|---|---|
| C0.1 | Baseline commit + skeleton | DONE 2026-10-28 (T-001 PASS) |
| C0.2 | (Hil) round-3 writer audit `python -m writer_test.run --model gemma4:e4b --audit 20` | counts in STATE.md; any "wrong" -> new check first |
| C0.3 | Planted-error tests for `tools/watch.py` (T-002) | each of 8 flags fires on its planted case; clean change -> none |
| C0.4 | Local services: Docker Desktop, PostgreSQL 16 + pgvector, Neo4j Community, compose profiles | NUMERIC round-trips Decimal exactly; planted: a float column is detected by a schema check |
| C0.5 | User requirements + risk assessment (1 page, GAMP 5 style) + golden test set list | every later chunk cites a requirement id |

## Phase 1 - Data spine on PostgreSQL + Neo4j, no model
| C | What | Done when / planted error |
|---|---|---|
| C1.1 | Fact schema: id, Decimal value, unit, batch, test, condition, month, source pointer (doc, version, page, box/cell), lineage, definition | JSON round-trip; planted: float value / missing source rejected |
| C1.2 | Postgres fact store; the write gate is the ONLY write path (DB role without direct INSERT) | planted: direct insert refused |
| C1.3 | Gate part a: schema contract, unit rule table, plausible ranges, quarantine with reason | planted: unit swap, decimal shift, missing batch -> quarantined; 0 good rows rejected |
| C1.4 | Gate part b: agreement of independent routes (copy never counts; unknown lineage = copy) + drift check (scheduled re-read vs store) | planted: copy as 2nd source, changed source -> review item |
| C1.5 | Evidence graph from day one: Neo4j primary + Postgres backup filled from the same gate; drift check between them | planted: node edited in one store only -> mismatch reported |
| C1.6 | Lek loader (`Laboratory.csv`, typo column) -> facts | counts match CSV; 20 impurity > total batches quarantined |
| C1.7 | Drugs@FDA PDF loader (PyMuPDF word boxes) for the Kerendia chemistry review; values typed twice blind where the PDF needs a person | every fact has page + box; planted: one mistyped value caught |
| C1.8 | DailyMed SPL XML label loader with versions (2021 vs July 2025, 40 mg) | conflict stored as 2 sourced facts with versions |
| C1.9 | Stats 1: mean/SD/%RSD, spec comparison, Decimal ROUND_HALF_UP | `round(0.125,2)` trap; matches NIST StRD digits |
| C1.10 | Stats 2a: ICH Q1E regression + one-sided 95% bound shelf life, extrapolation limit | matches statsmodels; planted: two-sided bound, month off by one -> tests fail |
| C1.11 | Stats 2b: poolability at 0.25 | planted: non-poolable batches pooled -> fails |
| C1.12 | Stats 3: OOT prediction interval, `<LOQ` policy | missing points, ties, <LOQ edge cases |
| C1.13 | Independent reference: R (expirest) cross-check + NIST StRD for all stats | agreement to documented digits; planted deviation detected |
**Checkpoint A0:** `python -m ectd_engine.demo_facts`: Lek fact with source row, Kerendia fact with page box, label version conflict, planted bad row quarantined, graph and Postgres agree.

## Phase 2 - Knowledge layer (retrieval only QUOTES)
| C | What | Done when / planted error |
|---|---|---|
| C2.1 | ICH corpus (M4Q, Q1A(R2), Q1E, Q3B(R2), Q6A) with table-aware chunking | every chunk keeps doc, page, table id |
| C2.2 | Hybrid retrieval: BM25 (Postgres FTS) + EmbeddingGemma vectors (pgvector) + mxbai-rerank | recall@5 on 30 hand questions; planted: number from retrieval used as a limit -> blocked |
| C2.3 | Citations: every quote verified verbatim against the source page | planted: altered quote rejected |
| C2.4 | Versioned rule table (thresholds entered twice, tested on guideline examples) | planted: single-entry or mismatched threshold rejected |

## Phase 3 - Writer on the fact store
| C | What | Done when / planted error |
|---|---|---|
| C3.1 | Port writer_test facts/validator/rendercheck (writer_test/ stays frozen) | 43 ported tests + mutation test pass |
| C3.2 | LLM client (Ollama Gemma 4 E4B / Kaggle 26B / mock) + structured outputs for extraction | mock 8/8; laptop run |
| C3.3 | Replay: port gives the same verdicts as the baseline on round-3 drafts | 100% same verdicts |
| C3.4 | 3.2.P.5.4 batch analyses (Lek): table + paragraph, own word lists + mutation kinds | 100% caught, 0 false rejects; audit >=100 accepted, 0 wrong |
| C3.5 | 3.2.P.5.1/5.6 specifications + justification (limits from spec facts; retrieval quotes only) | same bar |
| C3.6 | Code-owned content plan + render .docx/HTML; every rendered number records its placement | required fact missing -> rejected; placement count = number count |
| C3.7 | Entailment check (reviewer flag, 5b) + independent re-read of the exported file | planted overclaim ("no new signals") flagged |
| C3.8 | Agent Skill for 3.2.P.8.3 stability writing | skill run = same validator verdicts as direct run |
| C3.9 | Module 2.3 quality summary paragraphs as a view over the graph | planted 2.3 vs 3.2.P.8 shelf-life mismatch caught |
**Checkpoint A:** CSV -> facts -> stats -> Gemma draft -> validator -> rendered doc; planted wrong number rejected; classmate plants 10 errors. 2-minute video.

## Phase 4 - Trust layer + full review UI
| C | What | Done when / planted error |
|---|---|---|
| C4.1 | Ledger: SHA-256 hash chain, append-only, write-once anchor file, signing key held outside the DB (local stand-in for KMS), verify script | manual row edit -> verify exits non-zero |
| C4.2 | Wire ledger to gate, graph, writer (model id, prompt hash), validator, human actions | one section run = verifiable chain |
| C4.3 | OpenTelemetry GenAI traces -> self-hosted Langfuse, trace hashes in the ledger | planted: edited trace no longer matches its hash |
| C4.4 | FastAPI backend: sections, facts, sources, verdicts, Part 11 e-signature (name, time, meaning) | API tests; planted unsigned approval refused |
| C4.5 | React shell: dossier view (status, proof score, owner, blockers first) | renders dossier tree with proof scores |
| C4.6 | Section workspace: serif canvas, Tiptap editor with fact chips (5 states), outline/checklist | planted mismatch chip turns red |
| C4.7 | Evidence panel: click chip -> CSV row or PDF page box (PDF.js), one-click fix from source fact | every number opens its source |
| C4.8 | Review queue: review by exception, risk-ranked, blind entry for high-risk values, challenge items | reviewer who copies the shown value fails the challenge item |
| C4.9 | Sign-off blocked while any check fails; signed export; ledger entry | blocked/allowed cases tested |
**Checkpoint B:** browser demo: click number -> source; failed check blocks signing; tampering breaks `verify`; outside errors round 2.

## Phase 5 - Whole-dossier consistency (the product edge, D3)
| C | What | Done when / planted error |
|---|---|---|
| C5.1 | Graph model complete: facts, claims, placements, derivations (code version, inputs) | lineage query answers "where is this value used" |
| C5.2 | Change propagation ("living dossier"): source change -> affected placements listed, placeholders updated, prose flagged | planted source change -> all placements found |
| C5.3 | Kerendia sources added: EPAR + EU SmPC, Health Canada clinical study reports (link, not re-host) | each fact tagged with document version |
| C5.4 | Kerendia consistency audit: strengths, storage, shelf life, dose, patient numbers across M3, 2.7, M5, US label, SmPC | 40 mg = version difference (not error); planted copy error caught |
| C5.5 | Label claim matrix: every label claim traced to study report / M3 fact | untraced claim flagged |
| C5.6 | Consistency map screen + free two-document consistency check (self-serve door) | upload 2 docs -> every mismatch with page refs |
| C5.7 | Demo: plant one wrong number in a drafted copy -> flagged, placements listed, prose queued, all in the ledger | **Checkpoint C** |

## Phase 6 - Module 5 and Module 4 data engines
| C | What | Done when / planted error |
|---|---|---|
| C6.1 | CDISC reader: .xpt (pyreadstat) + define.xml parser (CDISC Pilot 01, R Consortium pilot package) | variable metadata matches define.xml |
| C6.2 | SDTM re-derivation of headline numbers vs CSR (reuse s3_rederive.py); ADaM copy never independent | 762/762 flips, 520/520 swaps caught (s3 bar) |
| C6.3 | CSR results paragraph + 2.7.3 paragraph with placeholders, number words and quantifier checks | mutation test 100%; "218 Caucasian" trap handled |
| C6.4 | Agent Skills for CSR results and label section | same verdicts as direct runs |
| C6.5 | Module 4: public SEND example data (PHUSE) -> facts; 2.4/2.6 nonclinical summary paragraph | planted NOAEL/value error caught |
| C6.6 | 2.5/2.7 summaries as graph views | planted cross-module mismatch caught |
**Checkpoint E:** one drug (Kerendia) + data engines (Lek, CDISC, SEND), all through the same validator and graph.

## Phase 7 - Scans
C7.1 render Lek values as CoA scans at 4 qualities (reuse ocr_stress_test) · C7.2 reader 1: layout OCR with cell coordinates (Docling / Granite-Docling / PaddleOCR-VL locally) · C7.3 reader 2: blind VLM read (Gemma 4), independent family · C7.4 cross-check into the gate: grid binding + header check, typed parse, rules, zoom re-read · C7.5 measure: 0 wrong auto-accepted over >=5,000 values, % to a person · C7.6 real supplier CoAs fetched by hand (Sigma-Aldrich, BioSpectra), testing only · C7.7 GEPA on the CoA extractor scored by our own checkers. Planted: OCR stress-test misreads. **Checkpoint D0:** measured table in the repo.

## Phase 8 - Orchestration, connectors, sandbox
C8.1 LangGraph section pipeline + Postgres checkpointer + interrupt for human review · C8.2 MCP servers (official Python SDK): "LIMS" over CSV/Postgres, "DMS" over the PDF folder, read-only · C8.3 resume-after-kill; failed verification = non-retryable -> human queue (planted: retry-until-pass refused) · C8.4 Temporal wrap of the workflow with a durable human wait (sign-off) · C8.5 free-code sandbox in a Firecracker microVM (Linux/WSL2 with KVM), labelled non-GMP; planted: network or file escape blocked.

## Phase 9 - Module 1, regions, lifecycle, after submission
C9.1 Module 1 US/EU regional items as graph views · C9.2 multi-region reuse: US label vs EU SmPC differences listed and sourced · C9.3 eCTD v4.0 pre-publishing checks (structure, links, metadata) with hand-off to a publishing tool · C9.4 deficiency rule library from openFDA complete response letters · C9.5 question board screen: agency questions as cards with owner, due date, linked evidence, drafted answer (same no-number rule) · C9.6 commitments + post-approval change package (Kerendia 40 mg as the worked example). **Checkpoint F.**

## Phase 10 - AI optimisation and research
C10.1 GEPA for the writer prompts, offline, judged on held-out checks + human golden set · C10.2 QLoRA of Gemma 4 run as a measured experiment; adopted only if it beats the prompt-only pass rate (D17) · C10.3 LLM-JEPA research chapter: ~1B model on text <-> fact-JSON pairs from the rendered scans vs plain fine-tuning, on free Kaggle GPU.

## Phase 11 - Evaluation, product polish, security
C11.1 seeded-error study across all parts, builder errors vs outside errors reported separately · C11.2 the five §36 metrics + unverifiable numbers in exported files = 0 · C11.3 onboarding wizard screen (connect sources, map folders to eCTD tree, roles, first consistency check) · C11.4 Word add-in (Office.js task pane with fact chips and evidence) · C11.5 UX metrics: time to first output, reviewer minutes/section, rework rate, length vs expert, SUS > 70 with 5 testers · C11.6 security and privacy review (§19, §26): threat model, secrets, access roles · C11.7 shadow-style comparison: one section by hand vs with the tool, errors and minutes · C11.8 README, architecture diagram, evaluation report with honest limits, demo video, clean GitHub repo · C11.9 resume bullets + portfolio entry. **Checkpoint D.**

## Track K - Claude Code mastery (brain/08)
K1 after C0.3 · K2 after C1.1 · K3 after C1.3 · K4 after C1.7 · K5 after C1.12 · K6 after C3.1 · K7 after C3.2 · K8 with C8.2 · K9 after Checkpoint B · K10 after C11.8.
Rules: a K card is issued only after a PASS; any K card that edits settings.json must show a fresh ACTIVITY line in `watch.py status`; globs include `.claude/**`; the brain reads the current docs page first.

## Cut list
None. Behind schedule = longer timeline, same scope, same order.

## Decided 2026-10-28 (Hil)
- Stack follows the explainer: PostgreSQL + pgvector + FTS and Neo4j Community (SQLite proposal withdrawn).
- `ectd_engine/` new package, `writer_test/` frozen. UI: React + FastAPI + PDF.js + Tiptap.
- Consistency phase moved before scans and orchestration (nothing removed).
