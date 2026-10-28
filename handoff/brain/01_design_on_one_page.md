# 01 Design on one page (source of truth: archive/explainer_full.md, 38 sections)

## What it is
An AI platform that drafts and cross-checks pharma regulatory submissions (eCTD, Modules 1–5). Started as CMC/Module 3 (the most number-heavy part, best place to prove the method), scope widened (2026-10-14) to the whole dossier. Differentiator vs Weave Bio / Peer AI / Celegence / Veeva: **evidence-first** (every claim traces to a fact; cross-module consistency engine), not drafting-first.

## The rule
The language model never writes a number. Pipeline:
1. Extract candidate facts from every source, each with a source pointer.
2. Validate: unit, plausible range, agreement of INDEPENDENT routes (copies never count; unknown lineage = copy). Disagreement -> human queue.
3. Write gate -> fact store (single source of truth), nothing unchecked gets in; failed rows quarantined with reason.
4. Compute with a validated statistics library called as tools over fact IDs (trend, ICH Q1E shelf life, OOT prediction interval). Results are new facts that record inputs + code version.
5. Write: model gets facts by ID, writes prose with `[[placeholders]]`.
6. Check: validator + independent re-read of the finished text against the raw table. Words like all/every/no/none/only make a sentence a claim that code re-tests.
7. Human reviews (click a number -> see source cell), signs (Part 11 e-signature).
8. Hash-chained ledger (SHA-256, anchored in write-once storage, key in KMS) records every action, model call, tool call, data pull.
Only extraction and wording stay probabilistic; both are boxed in by checks.

## Evidence graph + consistency engine (the differentiator)
Holds facts, claims (linked to facts), placements (every place a fact/claim appears), derivations (code version, inputs). Rules: one fact identical across modules, label, regions. Source changes -> graph lists affected placements, placeholders update, prose is flagged for re-review ("living dossier"). Module 2, label, Module 1, regulator answers are views over the graph.

## Stack (production design)
| Layer | Choice |
|---|---|
| Orchestration | Temporal outside (durable waits for sign-off), LangGraph 1.2.x inside model steps, Postgres checkpointer. Temporal history is NOT the GxP record. |
| Storage | Write gate -> graph primary at v1 (lineage queries) + PostgreSQL backup from same gate; pgvector + full-text. Student build: Postgres + Neo4j Community. |
| Retrieval | BM25 + EmbeddingGemma 2 + mxbai-rerank-v2, table-aware chunking; retrieval only QUOTES guidelines, never supplies limits |
| Scans | Layout OCR (Textract Tables / Docling) + independent VLM (Gemini 3.8 Flash / Gemma 4), blind reads, grid binding, typed parse, rules, zoom re-read |
| Stats | Pre-validated library (NumPy/SciPy/statsmodels, Decimal rounding); free code only in Firecracker microVM, labelled non-GMP |
| Models (prod) | Opus 5.5 drafting + GEPA reflection, Sonnet 5.5 fallback, Haiku 5.5 routing; EU via Bedrock eu. profiles |
| Models ($0 build) | Gemma 4 E4B on laptop (Ollama), Gemma 4 26B on free Kaggle T4x2; Claude app for hand comparisons |
| Prompts | GEPA offline, judged on held-out checks + human golden set |
| Tracing | OpenTelemetry GenAI -> Langfuse, hashed into ledger |

## Wrong-binding defence (writer; implemented in writer_test)
Model may pick a real fact but put it where it doesn't belong. Defence = (1) compound result facts carrying their own batch+month, (2) closed vocabulary: role/test/condition/batch/time/cause words only next to a placeholder with that role, sentence may only start with a safe connective or the attribute name, (3) code decides trend/compliance/must-mention facts and rejects contradicting words, (5a) independent re-read of finished text vs raw table. Reviewer flag: entailment check (5b). Reserve: code-owned content plan; grammar-constrained decoding only if too many drafts are rejected.

## Product experience (explainer §34)
Principles: show proof (chip states, per-section proof score); review by exception; outline first; less rework; preview consequences of a change; Word add-in; first value in a day; compliance that feels normal; one screen per role. Six screens: dossier view, section workspace (serif canvas, fact chips), review queue, consistency map, question board, onboarding wizard. Metrics: time to first output, reviewer minutes/section, rework <10–25%, length within 20% of expert, 100% seeded-error catch (incl. errors written outside the team), SUS > 70.

## Left out on purpose
RL fine-tuning of the writer, self-organising agent swarms, cross-product agent memory, free-roaming agents. JEPA = optional research track only.
