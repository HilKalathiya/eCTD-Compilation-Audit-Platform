# AI Evidence Engine for Drug Approval Dossiers — Technical Brief

Oct 14, 2026 · @hil

An AI system that drafts and audits the documents a drug company submits to regulators for approval. One hard rule shapes the whole design: the language model writes the words, but every number and claim comes from verified source data, is checked by code, and is signed off by a person.

## 1. Background: the drug approval dossier

Before a drug can be sold, the company must send the regulator (FDA in the US, EMA in Europe) a dossier proving the drug is safe, effective and made consistently. The format is the **eCTD** (electronic Common Technical Document), set by the international body ICH. One application is thousands of documents, often tens of thousands of pages, built from data spread across many systems.

| Module | What it holds | Examples |
| --- | --- | --- |
| 1 | Regional forms (differs per country) | Application form, cover letter, drug label |
| 2 | Summaries of Modules 3 to 5 | Quality summary (2.3), clinical overview (2.5) |
| 3 | Quality, called **CMC** (Chemistry, Manufacturing and Controls) | How the drug is made and tested, its specifications, stability data |
| 4 | Nonclinical (lab and animal) study reports | Toxicology, pharmacology |
| 5 | Clinical study reports | Trial reports, patient-level datasets |

The system covers all five modules. It starts with Module 3, because CMC is the most number-heavy part and the easiest place to prove the method, then extends the same engine to Modules 4, 5, 2 and 1.

## 2. The problem in technical terms

Today, writers copy numbers by hand from lab systems and PDFs into Word documents. The same fact (a shelf life, a dose, the number of patients treated) appears in many places across modules and the label, and every copy must match. A wrong or inconsistent number leads to regulator questions, delays or rejection; 74% of the 202 FDA rejection letters published for 2020 to 2024 cited quality or manufacturing problems.

The data sits in many systems:

- **LIMS** (lab results), **chromatography software** (Empower), **ELN** (lab notebooks), **ERP** (SAP).
- **PDFs from contract manufacturers**, such as Certificates of Analysis (CoAs), often scanned.
- **Clinical and nonclinical datasets** in CDISC formats (SDTM, ADaM, SEND) and statistical output tables.

A plain LLM or RAG chatbot cannot do this job safely:

| Requirement | Why a plain LLM or RAG fails | What this design does |
| --- | --- | --- |
| Every number exactly right | The model is usually right when copying or calculating, and “usually” cannot be validated | The model never writes a number; values come from a verified fact store (section 3) |
| Proof of source | Model-generated citations and page coordinates can be invented | Provenance is attached by the system from the fact record |
| Tables and scans | Text chunking breaks tables; OCR alone misses layout; a VLM alone misreads digits | OCR and VLM must agree before a value is accepted (section 5) |
| Same fact everywhere | RAG retrieves passages; it does not know two passages state one fact | An evidence graph links every placement of a fact (section 3) |
| Regulatory compliance | Free-roaming agents take different paths each run and cannot be validated; 21 CFR Part 11 requires audit trails and e-signatures | A fixed workflow with bounded AI steps, a tamper-evident ledger and human sign-off (section 7) |

## 3. The core idea: facts first, plus an evidence graph

**Rule: the language model never produces a number.** Numbers live in a database of verified facts. The model only writes the words around them. This turns a probabilistic AI problem into ordinary software that can be unit-tested and validated.

A **fact** is one reported value plus everything needed to trust it: value, unit, batch, test, time point, source system and source location (a LIMS row, or a box on a scanned page). The pipeline:

1. **Extract** candidate facts from every source, each with its source pointer.
2. **Validate** them: known unit, plausible range, and the same value from two routes (LIMS says 0.11, the scanned CoA also says 0.11). Disagreements go to a human queue.
3. **Store** them in one fact store, the single source of truth.
4. **Compute** with fixed, tested functions over fact IDs (trend slope, shelf-life estimate). Results become new facts that record their inputs and code version.
5. **Write**: the model gets facts by ID and writes with placeholders, for example `Total impurities at Month {{F-482.timepoint}} reached {{F-482}}, within the limit of {{F-482.limit}}.` A renderer fills in the values using the specification's rounding rule.
6. **Check**: a validator scans the final text. Every digit must trace to a fact, and every claim such as “all batches met specification” is re-tested by code.
7. **Review and sign**: a person clicks each number, sees its source, and signs.

Only two steps stay probabilistic: extraction (caught by the two-route cross-check and review) and wording (caught by the claim check).

**Widened to the whole dossier: every claim traces to evidence.** Three kinds of claim, each with its own check: numeric claims must match a fact; qualitative claims (“no new safety signals”) must point to the evidence they summarise and are rule-checked where possible; cross-references (“see Section 2.7.4”) must resolve to a real place in the dossier.

**The evidence graph** holds four things: **facts**, **claims** linked to the facts behind them, **placements** (every spot in the dossier where a fact or claim appears) and **derivations** (which code version produced which value from which inputs). Consistency rules run over it:

| Fact | Appears in | Rule |
| --- | --- | --- |
| Dose and regimen | Protocols, study reports, Modules 2.5 and 2.7, label section 2 | Identical everywhere |
| Patients exposed | Module 2.7.4, integrated safety summary, label section 6 | Identical, taken from the subject-level dataset |
| Shelf life and storage | Module 3.2.P.8, Module 2.3, label section 16 | Identical |

When a source changes (a corrected dataset, a new stability time point), a graph query lists every placement that depends on it. Placeholders update themselves, the surrounding prose is flagged for re-review, and the change is logged. This is the “living dossier”; today people do this impact check by searching hundreds of documents.

## 4. Architecture

&#91;embedded content: System architecture · 9 steps around one fact store\]

Data flows down the middle. Company data enters through MCP connectors; scans are parsed and cross-checked while structured rows pass straight through; everything lands in the fact store and evidence graph. Statistics, rules and the writer all read from it, the validator checks the draft against it, and a person signs before export. The orchestrator on the left runs each step in order; the ledger on the right records every one.

## 5. Where AI is used, and why each choice

AI does the parts that need understanding (reading messy pages, finding the right guideline text, writing prose). Code does the parts that must be exact (numbers, comparisons, logging). Each AI step is bounded and checked.

| Component | Technique | Why this choice |
| --- | --- | --- |
| Reading scanned PDFs | Layout-aware OCR (Docling, PaddleOCR-VL) plus a vision-language model (VLM). The VLM interprets the table and points to OCR word IDs; a value is accepted only if both agree | OCR alone misses merged headers, multi-page tables and unit footnotes. A VLM alone can misread a digit and gives imprecise coordinates. Born-digital PDFs skip AI and use PyMuPDF |
| Fact extraction output | Structured outputs: a JSON schema compiled into a grammar | Every fact proposal is valid JSON with the right fields. Ranges are still checked in code |
| Finding guideline text | Hybrid RAG: BM25 and dense embeddings in parallel, merged by reciprocal rank fusion, reranked, filtered by guideline version and region. Table-aware chunking. ColPali to search page images | Meaning questions need embeddings; codes and IDs (“Q3B”, “AM-102”) need exact keyword match. Chunking must not split tables |
| Quoting guidelines | Citations mode: answers point to exact passages and pages | Every regulatory statement shows the exact ICH text it relies on |
| Relationships | Knowledge graph built by deterministic code from structured data (Postgres first, Neo4j for lineage queries) | Multi-hop questions such as batch genealogy and “which sections cite results from method version 3?”. An LLM never invents edges between facts |
| Calculations | No LLM. A validated statistics library exposed as tools; the model picks the function and fact IDs, e.g. `shelf_life(fact_ids, spec_limit)` | Arithmetic must give the same answer every time and be unit-tested. Raw values never pass through the model |
| Orchestration | LangGraph 1.x: a typed state machine with checkpoints in Postgres and human-in-the-loop interrupts. Mostly fixed workflow, model freedom only inside bounded steps | Predictable paths can be validated. Free-roaming multi-agent frameworks (CrewAI, AutoGen-style chats) take different paths each run |
| Access to company systems | MCP (Model Context Protocol): one server per system (LIMS, document store) with typed tools | Vendor-neutral, so the same connectors work with any model; agents discover tools and argument types |
| Drafting | Frontier LLM with long context and vision, version-pinned. One Agent Skill per section type (template, required tables, phrasing rules). Writes with fact placeholders only | Strong scientific writing; a skill can be reviewed by experts like a written procedure |
| Claim checking | LLM extracts claims from the draft; code re-tests each against the facts and the graph | The model finds the claims, code decides if they are true |
| Improving prompts | GEPA (`dspy.GEPA`), offline. It reads the checkers' error messages (“extracted 0.14, expected 0.014; decimal shifted”) and rewrites the prompts. The winner is frozen and version-pinned | In its paper it beat RL fine-tuning (GRPO) by about 6% on average with up to 35× fewer runs, and it changes no model weights, so nothing needs re-validating except the prompt |
| Private deployment | Local open-weights model served by vLLM where data cannot leave the company network | Some data (trade secrets, patient data) must stay inside |
| Tracing | OpenTelemetry GenAI traces sent to Langfuse and hashed into the audit ledger | Every model call, tool call and retrieval is recorded in a standard format |

**Left out on purpose:** reinforcement-learning fine-tuning (every weight change means re-validation), self-organising agent swarms (cannot be validated), and long-term agent memory across products (risks carrying one drug's facts into another's dossier).

**Optional research track:** fine-tune a small (\~1B) local extractor with the LLM-JEPA loss on paired views (scanned table text and its verified fact JSON), and compare it with plain fine-tuning. JEPA stays out of the main path: it does not generate text or read documents better than current OCR and VLMs.

## 6. One request end to end: a stability section

The task: draft section 3.2.P.8.3 (Stability Data), which reports how the drug's quality changes over months of storage and supports its shelf life.

1. **Request.** The user picks the product, the section, the batches and a data-freeze date. The system proposes a data manifest (these studies, these batches, these documents); a person approves it.
2. **Fetch.** The orchestrator runs the manifest exactly through MCP tools, such as `get_stability_matrix` on the LIMS server and `get_documents` on the document store.
3. **Parse.** LIMS rows become facts directly. Scanned CoAs go through OCR plus the VLM with the two-route cross-check. LIMS and CoA values for the same result are reconciled; any disagreement goes to a human queue.
4. **Store.** Facts land in the fact store with their source pointer, and their links (batch, site, test, time point) go into the graph.
5. **Compute.** The statistics library fits the trend, estimates shelf life (ICH Q1E: where the 95% confidence bound of the regression line crosses the specification limit) and flags out-of-trend results with a prediction interval. Each result is stored as a derived fact with its code version.
6. **Rules.** Results are compared with specification limits in code. The relevant ICH guideline text is retrieved and quoted with citations.
7. **Draft.** The writer model drafts the section with placeholders. A renderer fills in values with the specification's rounding rule (`Decimal` with round-half-up; Python's built-in `round(0.125, 2)` gives 0.12, a classic silent bug).
8. **Check.** The validator confirms every digit traces to a fact, re-tests every claim, and checks cross-module consistency (the shelf life here must match Module 2.3 and label section 16). A failed check goes to a person; it is never auto-retried until it passes, because a model retried against a checker learns to satisfy the checker, not the truth.
9. **Review, sign, export.** The reviewer clicks each number, sees the exact source cell highlighted, and signs electronically. The signed document's hash goes into the ledger and the section is sent to the publishing system.

The same flow runs for other modules. In Module 5, for example, the facts come from the sponsor's validated statistical output tables, and the system re-derives the headline numbers from the ADaM datasets as an independent check.

## 7. Guardrails: validation, human sign-off, audit trail

Regulated software has to show what it did, who approved it and that nothing was changed afterwards. The key US rule is **21 CFR Part 11** (electronic records and signatures).

- **Validator as a gate.** Any number that does not trace to a fact, or any claim that fails its check, blocks the section from being signed.
- **Human sign-off.** An accountable person signs each section. The e-signature shows name, date, time and meaning (“approved as author”), and requires re-entering credentials. Review is risk-based: a value pulled by API from a validated system needs a lighter check than one read from a blurry scan.
- **Tamper-evident audit ledger.** An append-only Postgres table where each entry stores a SHA-256 hash of itself plus the previous entry's hash, so any edit breaks the chain. The latest hash is anchored in write-once storage, and entries are signed with a key held in a key-management service. It logs every user action, every model call (exact model ID, prompt, output), every tool call, every data pull with checksums, and the code version of the statistics library.
- **Pinned models and prompts.** Each model and prompt version is validated for its job. Changing either is a controlled, logged change, never a silent fallback.
- **Prompt-injection defence.** A document can carry hidden instructions. Tools are read-only, accounts have least privilege, each agent has an allow-list of tools, and every call is logged.
- **No memory across products.** Each run starts only from its approved data manifest.
- **Patient data (Modules 4 and 5).** Data minimisation, blinding firewalls and GDPR-compliant handling.
- **Single-tenant deployment.** Each customer gets its own isolated cloud environment (US or EU region), with single sign-on through the company's own identity system.

## 8. Evaluation: how we prove it works

Raw accuracy is the wrong headline. Even 99.5% field accuracy on a CoA with 200 values leaves about one error per document. The metric that matters is **zero undetected errors**: every wrong value is either caught by a check or flagged for a person.

| Metric | Target | How it is measured |
| --- | --- | --- |
| Wrong extractions that were flagged (recall of the cross-check) | 100% | Synthetic scanned CoAs with known ground truth |
| Seeded errors caught | All of them | Plant decimal shifts (0.14 vs 0.014), unit swaps, LIMS-vs-CoA mismatches, impossible dates, cross-module mismatches |
| Unverifiable numbers in final drafts | 0 | Validator report on every signed section |
| Statistics vs an independent reference | Exact match | Compare with R or statsmodels on edge cases: missing time points, values below the quantitation limit, rounding ties |
| Ledger tamper detection | Every manual edit detected | Edit a row by hand and run the verify script |
| Draft quality | Rework falls release on release | Share of generated text reviewers change, and length compared with expert-written examples |

## 9. Build plan: the student-scale version

Real pharma systems are not available to a student, and they are not needed. A focused build that proves the core rule (every number verified and traceable) is the goal.

**Scope:** one fictional tablet, two Module 3 sections: 3.2.P.8.3 Stability Data and 3.2.P.5.4 Batch Analyses.

**Data, all synthetic with perfect ground truth:**

- A fake LIMS export (CSV): 12 batches × 2 storage conditions × tests (assay, two impurities, total impurities, dissolution), with realistic trends and noise.
- Fake CoA PDFs in three layouts, then blurred, skewed and noised to look scanned.
- Injected errors to test the checker.
- Public ICH guideline PDFs as the retrieval corpus.

| Layer | Choice |
| --- | --- |
| Fact store, vectors, keyword search | PostgreSQL with pgvector and full-text search |
| Lineage graph | Neo4j Community in Docker |
| PDF and OCR | PyMuPDF for digital PDFs; Docling or PaddleOCR-VL for scans |
| Vision and drafting model | Claude API (a Sonnet-class model to keep cost down), structured outputs, citations |
| Workflow | LangGraph 1.x with a Postgres checkpointer and a human-review interrupt |
| Connectors | Two small MCP servers (Python SDK): “LIMS” over the CSV, “document store” over a folder of PDFs |
| Statistics | NumPy, SciPy, statsmodels, with pytest tests and `Decimal` rounding |
| Prompt tuning | GEPA via DSPy, scored by the system's own checkers |
| Review screen | React, PDF.js and a Tiptap editor with fact chips |
| Ledger and tracing | Postgres hash chain with a verify script; OpenTelemetry traces into Langfuse |

**Build order:**

1. Synthetic data generator and fact schema.
2. LIMS path end to end: CSV → facts → statistics → stability table.
3. Drafting with placeholders, plus the number and claim validator.
4. Review screen with click-to-source.
5. Scanned CoA parsing with the OCR + VLM cross-check.
6. Ledger, LangGraph wiring, MCP servers.
7. GEPA tuning of the extractor and writer prompts.
8. Evaluation report with the metrics in section 8.

**Then the whole-dossier demo: three thin slices joined by one graph.** Add Module 5 (the public R Consortium Pilot 1 submission package of ADaM datasets) and label sections 6 and 14 for the fictional drug. Change one number in the clinical data, and the system flags the mismatch across the study report, Module 2.7.3 and the label, lists every affected placement, updates the placeholders and queues the prose for re-review, with every step in the ledger.

## Sources

- [FDA's 202 published rejection letters, 74% citing quality or manufacturing (Pharma Manufacturing)](https://www.pharmamanufacturing.com/all-articles/article/55302937/fdas-crls-reveal-74-of-applications-rejected-for-quality-manufacturing-issues)
- [21 CFR Part 11, electronic records and signatures (eCFR)](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11)
- [ICH Q1E, evaluation of stability data](https://database.ich.org/sites/default/files/Q1E_Guideline.pdf)
- [FDA draft guidance on AI for regulatory decision-making (Jan 2025)](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/considerations-use-artificial-intelligence-support-regulatory-decision-making-drug-and-biological)
- [Model Context Protocol joins the Agentic AI Foundation](https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/)
- [LangChain and LangGraph 1.0](https://www.langchain.com/blog/langchain-langgraph-1dot0)
- [GEPA: Reflective Prompt Evolution (arXiv, ICLR 2026)](https://arxiv.org/pdf/2507.19457) and [DSPy GEPA docs](https://dspy.ai/current/api/optimizers/GEPA/overview/)
- [LLM-JEPA (arXiv)](https://arxiv.org/html/2509.14252v2)
- [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) and [Claude citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Open-source OCR and document VLMs compared (Spheron)](https://www.spheron.network/blog/best-open-source-ocr-vlm-self-host-gpu-cloud-2026/)
- [ColPali visual retrieval (Hugging Face)](https://huggingface.co/blog/manu/colpali)
- [Agent Skills open standard (SiliconANGLE)](https://siliconangle.com/2025/12/18/anthropic-makes-agent-skills-open-standard/)
- [R Consortium Pilot 1 submission package (GitHub)](https://github.com/RConsortium/submissions-pilot1-to-fda)
