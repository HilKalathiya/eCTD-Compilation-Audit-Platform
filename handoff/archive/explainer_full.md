# eCTD Compilation & Audit Platform — Complete Explainer

Sep 30, 2026 · @hil Kalathiya

This project is an AI system that assembles and cross-checks the manufacturing section (CMC, eCTD Module 3) of a drug approval filing, so that every number in the dossier is pulled from raw lab data, verified by code, traced to its exact source location, and signed by a human. Where the detailed overview is wrong or overclaims, this doc says so and gives the fix — look for the **Check:** notes, each followed by its **Fix:**.

**Scope:** the project started with CMC (Module 3) and now covers the whole eCTD, Modules 1 to 5. Module 3 is the first engine to build and the worked example throughout; the same design extends to every module.

**How to read this doc:** top to bottom. Each part builds on the one before it.

| Part | Sections | What you will understand |
| --- | --- | --- |
| 1. The big picture | 1 | What the project is, on one page |
| 2. The world and the problem | 2–5 | Drug approval, the eCTD and CMC; today's manual workflow; why existing tools fail; competitors |
| 3. The core idea | 6–9 | Facts first; widening it to every claim; the evidence graph; the whole platform at a glance |
| 4. The first engine: Module 3 | 10–20 | Each component, why it was chosen over the alternatives, and one request end to end |
| 5. Every other module | 21–26 | Modules 4, 5, 2 and 1, labeling, publishing, after submission, rules for patient data |
| 6. Technology and timing | 27–29 | Why now, the latest GenAI and agent technologies, coming data standards |
| 7. Risks, plan and business | 30–34 | Technical challenges and an audit of checks that cannot fail, roadmap, market, how this differs from Weave Bio, product experience and design |
| 8. Review and build | 35–36 | Every error in the original overview, and the student-scale build |
| Appendix | 37–38 | Glossary, sources |

## 1. The project on one page

Before a company may test a drug in people or sell it, it must prove to regulators that it can **make** that drug the same way, batch after batch. That proof is a dossier of thousands of numbers (eCTD Module 3). Today humans copy those numbers by hand from lab systems and scanned PDFs into Word, and one typo can stall an approval. This project builds that dossier automatically and audits it, and a human still signs.

**Scope:** the platform covers every module of the eCTD. It starts with Module 3 (CMC), the most number-heavy part, and the same design then extends to animal studies (Module 4), clinical studies (Module 5), the summaries (Module 2), the label and the regional Module 1 (sections 7–9 and 21–26).

Taking Module 3, the first engine, as the example:

| What goes in | What comes out |
| --- | --- |
| Stability results from LIMS, chromatography results from Empower, lab notes from the ELN, batch records from SAP, scanned Certificates of Analysis from contract manufacturers | Draft Module 3 sections (for example 3.2.P.5 Control of Drug Product, 3.2.P.8 Stability) in which every number links to the exact cell it came from, a verification report, and a tamper-evident audit trail |

**Who uses it:** regulatory medical writers (drafting), QA auditors (checking), and the regulatory lead (signing).

**The single idea everything serves:** a language model is good at reading messy documents and writing scientific prose, and bad at being the source of truth for a number. So the system splits the work:

1. Extraction turns every source into **facts** (value + unit + batch + test + condition + time point + exact page and box it came from).
2. **Code**, not the model, does every calculation (means, trends, limits).
3. The model **writes prose around verified facts**; it never types a digit itself.
4. A checker rejects any number in the draft that does not match a stored fact.
5. A **human** reviews every number against its source and signs; every step is logged.

**The five building blocks** (the overview's names in brackets):

1. Connectors that pull data from company systems \[MCP servers\].
2. Parsers that turn scanned PDFs into tables with coordinates \[vision-language pipeline\].
3. A knowledge store that remembers how batches, tests, conditions and results relate, and searches regulations \[Neo4j + Pinecone\].
4. A coordinator that runs the steps and the specialist agents \[LangGraph supervisor\].
5. A review screen and an audit ledger \[provenance workspace + Part 11 ledger\].

**What it is not:** it does not make regulatory decisions, does not file with FDA itself (it hands finished sections to Veeva Vault, which publishes and submits), and does not replace QA sign-off.

**Verdict on the two overview docs, in short:** the problem analysis is strong and mostly accurate. The architecture points the right way but is overloaded with brand names, contradicts itself on data sovereignty, names at least one component that does not exist, and contains a few pharmaceutical science errors. Section 35 lists every one with its fix.

## 2. The world it lives in

To get a drug approved, a company must prove three things: it works, it is safe, and it can be **made with consistent quality**. The third is called CMC (Chemistry, Manufacturing and Controls), and it is the only part this project touches.

**The path of a drug and where CMC is filed:**

1. Discovery and animal studies.
2. **IND** (Investigational New Drug application): permission to start human trials. It already needs a CMC section, smaller in early phases.
3. Phase 1, 2, 3 clinical trials. The CMC section grows as manufacturing scales up.
4. **NDA** (New Drug Application, for chemically made "small molecule" drugs) or **BLA** (Biologics License Application, for drugs made in living cells, such as antibodies and vaccines): permission to sell. The full CMC dossier goes in here.
5. **Post-approval changes**: every later change to a site, process, supplier or test method needs a supplement with updated CMC data.

**Small molecule vs biologic matters for this project,** because different rules apply. A small molecule (aspirin-sized, made by chemical synthesis) follows ICH Q3A/Q3B for impurities. A biologic (a protein roughly 1,000 times heavier, grown in a bioreactor) follows ICH Q6B and Q5C instead. The overview mixes the two; section 20 shows where.

**The eCTD** (electronic Common Technical Document) is the standard format FDA, EMA, Japan's PMDA and others accept. It has five modules; the overview's diagram shows only three.

| Module | What it holds | Same in every region? |
| --- | --- | --- |
| 1 | Forms, labeling, cover letter | No, regional |
| 2 | Summaries; 2.3 is the Quality Overall Summary (QOS) of Module 3 | Yes |
| 3 | Quality / CMC data, the target of this project | Yes |
| 4 | Animal study reports | Yes |
| 5 | Clinical study reports | Yes |

Module 2.3 re-states Module 3's key numbers in short form. That is why "Module 2 and Module 3 disagree" is a classic error: the same number lives in two places, typed twice.

&#91;embedded content: The whole eCTD · 5 modules\]

The CTD is usually drawn as a pyramid: Modules 3, 4 and 5 are the full evidence (quality, animal studies, human studies), Module 2 condenses each into overviews and summaries, and Module 1 wraps it all in region-specific forms and labeling. Structure from [ICH M4](https://database.ich.org/sites/default/files/M4_R4__Guideline.pdf).

**Inside Module 3** (the ICH M4Q layout), with the source systems each part draws on:

| Section | What it proves | Typical data sources |
| --- | --- | --- |
| 3.2.S Drug Substance | The active ingredient: how it is made, characterized, tested (S.4), how long it stays stable (S.7) | ELN, MES/ERP batch records, LIMS, Empower |
| 3.2.P Drug Product | The finished medicine (tablet, vial) | Same, plus formulation data |
| 3.2.P.5 Control of Drug Product | Specifications (P.5.1), test methods (P.5.2), method validation (P.5.3), batch results (P.5.4), impurity characterization (P.5.5), why the limits are justified (P.5.6) | LIMS, CoAs, Empower |
| 3.2.P.8 Stability | Shelf life, from years of storage tests | LIMS stability module |
| 3.2.A Appendices | Facilities (A.1), virus and contamination safety (A.2, key for biologics), new excipients (A.3) | QA documents |
| 3.2.R Regional | Region-specific items, such as executed batch records for FDA | ERP / MES, QA |

**Vocabulary you will meet everywhere:**

- **Batch / lot**: one production run, with an ID like 2024-07.
- **Specification**: the list of tests and pass limits for a batch, for example "Assay 95.0–105.0% of label claim".
- **CoA (Certificate of Analysis)**: one batch's test results against its specification. Contract manufacturers (**CMOs**) send these, often as scanned PDFs.
- **Assay / potency**: how much active drug is present, or how strongly it acts.
- **Impurity / degradation product**: unwanted substances from manufacture or from the drug breaking down over time.
- **Stability study**: samples stored at set temperature and humidity and tested at fixed months to set shelf life. Small molecules: long-term 25°C/60% RH, accelerated 40°C/75% RH for 6 months. Biologics: usually 5°C long-term.
- **OOS vs OOT**: out-of-specification means a result broke a limit (a formal investigation follows). Out-of-trend means it is still within limits but breaks the batch's own pattern, an early warning.
- **HPLC**: a lab instrument that separates a sample into components. Each component is a peak on a chart (a chromatogram); peak area gives the amount.
- **cGMP**: current Good Manufacturing Practice, the legal quality rules for manufacture.
- **21 CFR Part 11**: the US rule for when electronic records and signatures count as trustworthy (section 18).
- **ICH**: the body that writes the shared technical guidelines (Q1 stability, Q2 method validation, Q3 impurities, Q5/Q6 biologics, and so on).

**The people involved:** Regulatory Affairs owns the submission. TechOps/MSAT engineers run and scale the process. Analytical Development and QC run the tests. QA audits compliance. Medical writers turn data into narrative. Regulatory Operations (publishing) assembles the eCTD. CMOs are outside companies that make batches and send CoAs.

## 3. The actual problem

The hard part is not writing sentences. It is keeping thousands of numbers identical across hundreds of tables, when each number was copied by hand from a different system. One major filing draws on roughly 500 to 5,000 source documents (the overview's figure, plausible for a BLA).

**Today's workflow, and where each step breaks:**

| # | Step | Who | Tools | What typically goes wrong |
| --- | --- | --- | --- | --- |
| 1 | Plan sections, set the data-freeze date | RA project manager | Smartsheet, Teams | The freeze slips; new data lands after tables are already written |
| 2 | Pull raw data | QC scientist, MSAT lead | Empower, LIMS, Benchling, SAP, CMO portals | Exports taken on different dates; CMO results arrive as scans |
| 3 | Consolidate into Excel | Medical writer | Excel, Acrobat | Re-keying errors, unit mix-ups (µg/mg vs %w/w) |
| 4 | Write the narrative | Medical writer | Word, Veeva | Text says "all results met specification" while a table shows one that did not |
| 5 | Recalculate statistics | QC auditor | Excel | Formula drift, inconsistent rounding |
| 6 | Check every number against source | QA auditor | Acrobat, highlighters, two monitors | Fatigue: thousands of numbers checked by eye; errors loop back to step 3 |
| 7 | Publish the eCTD | Regulatory operations | Vault RIM, docuBridge | Broken links, wrong document lifecycle |
| 8 | Sign and submit | VP Regulatory, QA head | Vault, FDA gateway | A late-found error forces re-work of everything downstream |

Steps 3 to 6 are what this project automates. Steps 1, 7 and 8 stay human-led, with the system feeding them.

**Where the errors come from:**

- **Transcription**: 0.14% typed for 0.014%.
- **Units**: the same impurity reported in %, ppm or µg/mg by different labs.
- **Version drift**: LIMS was corrected after the Word table was built.
- **Duplication**: one number lives in 3.2.S, 3.2.P and Module 2.3, typed separately each time.
- **Rounding**: results must be rounded to the specification's decimal places; people and Excel round differently.
- **Missed trends**: a slow rise in an impurity across 24 months that no one plotted.

**What it costs, with the overview's numbers checked:**

| Overview claim | What the evidence says | Verdict |
| --- | --- | --- |
| Delay costs "$1M to $3M per day" | Tufts CSDD (2024): about $800K per day in lost sales on average; medians of $1.4M (cardiovascular), $1.3M (hematology), $840K (oncology) | True for big drugs only; use \~$0.8M as the average |
| One decimal error causes a Refuse-to-File (RTF) letter | RTF is decided within 60 days of submission and is meant for applications so incomplete that review is impossible. A single wrong number more often triggers an Information Request, or questions that pile into a Complete Response Letter at the end | Overstated |
| An IR or RTF "halts the review clock for 30 to 90 days" | Information Requests do not stop the clock. A large response can count as a major amendment, which pushes the goal date out 3 months. An RTF is worse: you fix and resubmit, and the clock restarts | Imprecise |
| "Up to 12,000 human hours per filing" | No public source found | Treat as an assumption |
| 6 to 12 months to compile a major filing | Consistent with industry descriptions | Plausible |

For an IND the equivalent risk is not RTF but a **clinical hold**: FDA has 30 days to object before trials may start.

**The deeper risk is credibility, not one typo.** FDA expects data to meet **ALCOA+**: Attributable, Legible, Contemporaneous, Original, Accurate, plus Complete, Consistent, Enduring and Available. A reviewer who finds numbers that do not match starts doubting everything else in the file. That is why the project's core promise is **traceability**, not speed: every number must lead back to the original record.

## 4. Why the problem persists

The data is split across five or six systems that were never designed to talk to each other, and each one is a **validated** system that companies are afraid to touch. Here is each system, in plain words:

| System (example product) | What it is | What it holds for CMC | How data gets out | Why it hurts |
| --- | --- | --- | --- | --- |
| CDS: Waters Empower 3 | Software that runs HPLC instruments and stores raw signals and peak results | Peak areas, % impurities, assay values, chromatograms | PDF/CSV reports; the Empower Toolkit programming interface, which lab-data platforms such as TetraScience use to pull results as JSON | No simple REST API, so the overview is right that it is hard, but "no hooks at all" is too strong |
| LIMS: Thermo SampleManager, LabWare | Tracks every sample, test, result and specification | Release results, stability study matrices, specs | SQL views, XML/CSV exports, REST on newer versions | Each site configures its own fields, so the same test has different names |
| ELN: Benchling | Digital lab notebook | Formulation and process development experiments | Good REST API (JSON) | Much of it is free text |
| ERP / MES: SAP S/4HANA, MES tools | Business and shop-floor execution systems | Batch genealogy, materials, sites, dates, batch records | SAP OData services and BAPIs | Batch records from outside manufacturers are often PDFs |
| DMS / RIM: Veeva Vault RIM, QualityDocs | Controlled-document and submission system | Reports, CoAs, final eCTD documents | REST API, webhooks | Knows a document's metadata and approval state, not the numbers inside it |
| CMO portals and email | Outside manufacturers | CoAs, batch records | Manual download | Scanned, every layout different |

**Five root causes:**

1. **Validation lock-in.** Every system above is validated for GMP use. Connecting or changing it means re-validation paperwork, so companies leave them alone and move data by export and copy-paste.
2. **Acquisitions.** A company that bought three biotechs may run three different LIMS, each configured differently.
3. **Outsourcing.** CMOs do not give sponsors access to their systems. They send PDFs. The overview's "over 60% of CMO data arrives as scans" has no source, but the direction is right.
4. **Data-integrity rules.** FDA's cGMP rules and its data-integrity guidance expect every reported result to be attributable to an original record (ALCOA+). A script that silently copies numbers is itself a GMP system that must be validated and audited, so "just automate it" is not allowed without the audit machinery this project builds.
5. **Nobody owns the seams.** Each department owns its own system. The cross-system consistency problem belongs to the writers and QA at the very end, when changes are most expensive.

**Check:** the overview credits traceability to 21 CFR Part 11 alone. Part 11 governs electronic records and signatures. The "trace every number to the raw result" expectation also comes from cGMP record rules (21 CFR 211) and FDA's data-integrity guidance. Worth saying correctly in an interview.

**Fix:** cite the full basis. Part 11 covers electronic records and signatures. 21 CFR 211.68 says only authorized people change records and backups must be exact and complete; 211.194 requires second-person review of lab records. FDA's 2018 [data integrity Q&A](https://www.fda.gov/media/119267/download) adds ALCOA and says the quality unit reviews audit trails. Build to match: unique logins, an audit trail nobody can edit, second-person sign-off, and a risk-based schedule for audit-trail review.

## 5. Why existing tools fail

Each older tool solves one slice. None of them both **understands** the content and **proves** every number. That combined gap is the project's opening, and in 2026 several AI companies are racing for it too.

| Tool family | What it does well | Where it breaks for CMC | Is the overview fair? |
| --- | --- | --- | --- |
| Document management (Veeva Vault RIM, MasterControl, Documentum) | Versioning, approval routing, e-signatures, eCTD publishing | Treats a document as a sealed box; never checks the numbers inside | Fair, but dated: Veeva announced in-product AI agents in May 2026 (see below) |
| Traditional OCR (Tesseract, older ABBYY) | Reads clean printed text | Tables of varying layout, multi-page tables, 1.2×10⁻³ read as "1.2x10-3", µ read as u, merged cells, tables printed over charts. Worst of all, it fails **silently** with a plausible wrong number | Fair for Tesseract. But it picks the weakest rival: modern layout-aware OCR (Azure Document Intelligence, AWS Textract, Google Document AI, open-source Docling) is much better and is a real alternative (section 12) |
| RPA (UiPath) | Repeats recorded clicks and copy-pastes | Breaks when a screen changes; cannot tell that "Related Substance A" and "Impurity 1" are the same compound; cannot judge | Fair. RPA can **move** data; it cannot **understand** or **verify** it |
| Chatbot LLM or basic RAG | Reads messy text, writes fluent prose | Arithmetic is not guaranteed; fixed 512-token chunks cut tables so values lose their column headers; no pointer to the source cell; can invent citations; answers change run to run and when the vendor updates the model | Fair. The last point, non-determinism, is the biggest problem for validation, and the overview barely mentions it |

**A note on the jargon.** The overview says chatbots lack "cryptographic bounding-box provenance linking every character to the pixel coordinate". In plain words the requirement is: every reported value must link to the exact place in the source record it came from, and that link must be tamper-evident. Sections 12 and 18 show how.

**What the overview leaves out: the 2026 competition.** "Existing solutions" is not just Veeva and OCR anymore.

| Company | What it offers | When |
| --- | --- | --- |
| [Celegence (CAPTIS)](https://manufacturingchemist.com/celegence-pioneers-industry-first-automation-of-cmc-module) | Generative-AI drafting of CMC Module 3. Pilot with Kenvue claimed 80–95% alignment with previously approved text and 60% faster drafts | Announced July 2025 |
| [SyncIQ](https://intuitionlabs.ai/articles/ai-cmc-authoring-software-comparison) | Module 3 and Module 2.3 drafts with synchronized cross-module consistency | On the market by mid-2026 |
| [Weave Bio](https://intuitionlabs.ai/articles/ai-cmc-authoring-software-comparison) | AI regulatory platform across Modules 1–5, NDA workflows co-developed with Parexel | On the market by mid-2026 |
| [Peer AI](https://intuitionlabs.ai/articles/ai-cmc-authoring-software-comparison) | Specialized agents for preclinical, clinical and CMC documents | On the market by mid-2026 |
| [Veeva](https://www.clinicaltrialvanguard.com/conference-coverage/veeva-unveils-falcon-ai-platform-and-agentic-authoring-at-2026-summit/) | Vault AI (Aug 2026), Falcon agentic platform (late 2026, early adopters), Agentic Authoring of submission documents (late 2027) | Announced May 2026 |

**What this means for the project:** "AI drafts Module 3" is no longer unique. The defensible edge is the part most drafting tools under-invest in: **deterministic verification of every number, cell-level provenance, and a validation-ready audit trail.** If you pitch this project, lead with that, not with drafting.

## 6. The core design principle: facts first, prose second

If you remember one thing about this project, make it this: **the language model never produces a number.** Numbers come from a store of verified facts; the model only writes the words around them. Every other component exists to fill, check, or display that fact store.

**What a "fact" is.** One reported value plus everything needed to trust it:

```json
{
  "fact_id": "F-000482",
  "value": "0.11",
  "unit": "%",
  "analyte": "Total degradation products",
  "test": "Related substances by HPLC, method AM-102 v3",
  "batch": "2023-02",
  "condition": "25C/60%RH",
  "timepoint_months": 36,
  "limit": "NMT 0.5%",
  "source": {"system": "LIMS", "record": "ST-2023-0412/R-7731", "doc": "Stability_report_2023-02.pdf", "page": 4, "bbox": [342, 110, 368, 280]},
  "lineage": ["Empower result 7731 (original)", "LIMS record R-7731 (copy)", "stability report p. 4 (printed from LIMS)"],
  "checks": {"lims_matches_empower": true, "report_matches_lims": true, "human_verified": false}
}
```

**The pipeline, in order:**

1. **Extract** candidate facts from every source, each with its source pointer.
2. **Validate** them: known unit, plausible range, and agreement with an independent route or with the original source (LIMS says 0.11, and the chromatography result in Empower that LIMS copied also says 0.11). A CoA printed from the same LIMS is a copy, not a second route: each fact records its lineage, and copies never count as agreement with each other (section 30). Disagreements go to a human queue.
3. **Store** them, only once they pass validation, in one database of record: the fact store.
4. **Compute** with fixed, tested functions over fact IDs (mean, trend slope, shelf-life estimate). Results are new facts that record which inputs and which code version produced them.
5. **Write**: the model receives facts by ID and writes text with placeholders, for example `Total degradation products at Month {{F-000482.timepoint}} reached {{F-000482}}, within the limit of {{F-000482.limit}}.` A renderer fills in the formatted values using the specification's rounding rules.
6. **Check**: a validator scans the final text. Every number must be a placeholder bound to one fact, and the batch, test, time point and unit around it must match that fact; a number that merely exists somewhere in the fact store is not enough. Results written in words (“three analytes”) are rendered from facts too, and words such as “all”, “every”, “no”, “none” and “only” turn a sentence into a claim, such as “all batches met specification”, that code re-tests (section 7). Anything unmatched blocks publication.
7. **Review and sign**: a human clicks each number, sees its source, and signs. Every step is logged.

**Why this is the right design:** it turns a probabilistic AI problem into a normal software problem that can be unit-tested and validated. Only two steps stay probabilistic: extraction (caught by cross-checks and human review) and the wording of prose (caught by claim checks, and never the evidence itself).

**Check: the overview leaves the model in charge of numbers in two places.**

- Its math example has the LLM **paste the data values into the Python script** by hand (`'impurity_pct': [0.01, 0.01, ...]`). If the model mistypes one value while writing the script, Python computes the wrong answer perfectly. Fix: the script loads values from the fact store by ID; the model never types them.
- Its provenance example has the **model emit the provenance JSON** (page, bounding box). A model can invent a plausible page and box. Fix: provenance is attached by the system from the fact record, never generated by the model.

Both fixes keep the overview's architecture and simply move the numbers out of the model's hands.

**Fix:** make it impossible, not just discouraged. Calculation tools accept fact IDs only, never raw numbers. Provenance fields are read-only and joined from the fact record when the text is rendered. A test seeds a mistyped value into a script and expects the validator to block it.

## 7. From numbers to claims: one rule for the whole eCTD

The project covers the whole eCTD, Modules 1 to 5, with Module 3 as the first engine. Everything in the Module 3 design carries over: the fact store, validated code for every number, the model writing with placeholders, the validator, human sign-off, the hash-chained ledger, MCP connectors, Temporal with LangGraph inside, GEPA. What changes is the **unit of truth**, the sources, and the hardest problem.

|  | Module 3 engine | Whole-eCTD platform |
| --- | --- | --- |
| Unit of truth | A **fact**: one number with its source | An **evidence item**: a fact, a claim, or a document reference, each linked to its source |
| Sources | LIMS, Empower, ELN, SAP, CMO certificates | Those, plus clinical data (EDC, SDTM/ADaM datasets, statistical outputs), nonclinical data (SEND, GLP study reports), the safety database, the labeling system, RIM and past regulator correspondence |
| Hardest problem | Every number matches its source | The **same** fact stays identical across five modules, the label and several regions, and every claim is backed by evidence |
| Who calculates | The validated statistics library | Clinical and toxicology statistics come from the sponsor's validated SAS/R programs; the platform reads and checks them, never recomputes efficacy results |
| Users | CMC writers, QA | Plus medical writers, biostatisticians, nonclinical scientists, labeling, regulatory operations, regulatory strategy |
| Data sensitivity | Trade secrets | Plus patient-level data, so privacy law now applies (section 26) |
| Output | Module 3 sections | A content plan, drafts for all modules, the label, cover letters, pre-publishing checks, answers to regulator questions |

**The rule, widened: every claim traces to evidence.** Three kinds of claim, each with its own check:

1. **Numeric claims** ("the response rate was 42.1%") must match a fact taken from a validated output table. Same mechanism as section 6.
2. **Qualitative claims** ("no new safety signals were observed") must point to the evidence set they summarize. Rules check them where possible (any serious adverse event of a new type contradicts the claim); otherwise they are flagged for expert sign-off.
3. **Cross-references** ("see Section 2.7.4", "Study 301") must resolve to a real place in the dossier.

**Who finds the claims.** If the model that drafts a sentence also decides which parts of it are claims, a claim it does not notice is never checked. So claims are extracted by a model from a different family plus fixed rules. Every sentence must end up as a number, a claim or a non-claim; non-claim labels are shown to the reviewer, and a sentence with “all”, “every”, “no”, “none” or “only” can never be marked non-claim. Words matter here: a real study report states several key safety results in words alone (section 30).

**One honest boundary:** the model now drafts in the most sensitive places, such as the clinical overview and the label. Benefit-risk conclusions are the sponsor's scientific judgment. The platform drafts, proves and flags; named experts own the conclusions and sign. That keeps the AI inside the "drafting a submission" use that FDA's draft AI guidance places outside its scope.

## 8. The evidence graph and consistency engine

This is the core differentiator. Competitors link sentences to their sources, and some reuse a value across a document set. This platform knows that "the dose in the label", "the dose in Study 301's report" and "the dose in the clinical overview" are **one fact**, stored once, shown in many places. Change it once and every place updates or gets flagged.

**What the graph holds:**

- **Facts**: single values with their source (a cell in an output table, a row in a dataset, a box on a scanned page).
- **Claims**: statements, each linked to the facts and evidence sets that support it.
- **Placements**: every spot in the dossier where a fact or claim appears (section, paragraph, table cell, label line, region).
- **Derivations**: which code, and which code version, produced a value from which inputs.

**Consistency rules, examples:**

| Fact | Appears in | Rule |
| --- | --- | --- |
| Dose and regimen | Protocols, CSRs, 2.5, 2.7, label section 2, cover letter | Identical everywhere |
| Number of patients exposed | 2.7.4, integrated safety summary, label section 6 | Identical, taken from the subject-level dataset (ADSL) |
| Primary endpoint result | CSR section 11, 2.5, 2.7.3, label section 14 | Identical to the output table, same rounding |
| NOAEL and safety margins | Module 4 reports, 2.4, 2.6, label sections 8.1 and 13 | Consistent; margins recomputed by code |
| Shelf life and storage | 3.2.P.8, 2.3, label section 16 | Identical |
| Composition and excipients | 3.2.P.1, label section 11 | Identical |
| Drug substance specifications | 3.2.S.4.1, 2.3.S | Identical |

(Label section numbers follow the US prescribing-information format: 2 dosage, 6 adverse reactions, 8 specific populations, 11 description, 13 nonclinical toxicology, 14 clinical studies, 16 storage.)

**Checking what actually ships.** If every placement is rendered from one fact, the graph agrees with itself by construction, which proves nothing about the files sent to the regulator: a hand edit in Word or a stale table would never show. So the consistency check re-reads the final exported documents with its own parser and compares what is printed. Each fact also carries its definition (population, coding list, method version, document version), because one name can mean two things: in a real trial's data, “White” is 230 patients while the study report's “Caucasian” is 218, since the report's form listed Hispanic as its own group (section 30).

**Change propagation, the "living dossier":** when a source changes (a corrected dataset, a new stability time point, a re-run table), a graph query lists every placement that depends on it. Values written as placeholders update themselves; prose around them is flagged for re-review; the change and its reach are logged. Today this impact check is done by people searching hundreds of documents.

**Why it is hard to copy:** the value grows with every module connected. A tool that only drafts documents has nothing to propagate through.

## 9. The whole platform at a glance

Three module engines and a content plan feed one evidence graph through the write gate; four writers turn that graph into documents; the validator, human review and existing publishing tools carry them to regulators.

&#91;embedded content: Whole-eCTD platform architecture\]

Modules 3, 4 and 5 hold evidence, so each gets an engine that turns raw sources into facts. Modules 1 and 2, the label and regulator answers are written **from** the graph, which is why they stay consistent. When regulators send questions, the answers go back through the same graph. Sections 10 to 20 now open up the first engine, Module 3, box by box; sections 21 to 26 cover the other modules.

## 10. The Module 3 engine at a glance

Everything is arranged around one database of verified facts. Data flows down the middle; a Temporal workflow on the left runs each step in order, with LangGraph inside the model steps, and a ledger on the right records every one.

&#91;embedded content: System architecture · 13 steps\]

Company data enters through MCP; scans are parsed, and structured rows are read as they are. Both land first in a staging area. A write gate checks every fact there (schema, units, copies, agreement with every other source) and only passing facts enter the fact store. Statistics, rules and the writer all read from it, the validator checks the draft against it, and a human signs before Veeva publishes. Sections 11 to 19 take each box in turn.

## 11. Integration layer: MCP

MCP is the right plug for letting agents reach company systems, but it does not remove the hard work behind the plug. Someone still writes the code that talks to Empower, LIMS and SAP.

**What MCP is.** The Model Context Protocol is an open standard, created by Anthropic in November 2024 and [donated on 9 December 2025 to the Agentic AI Foundation](https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/) under the Linux Foundation (co-founded with Block and OpenAI). It defines how an AI application (the **client**) discovers and calls functions (**tools**), reads data (**resources**) and uses templates (**prompts**) offered by a **server**. Each tool has a name and a typed input/output schema, for example `get_stability_matrix(study_id)`. At that announcement MCP had over 10,000 active servers and 97 million monthly SDK downloads, with support in Claude, ChatGPT, Gemini, Copilot and VS Code.

**Analogy:** MCP is a USB-C port. Every device uses the same plug shape, but each device still needs its own driver. Here, each enterprise system needs its own MCP server (the driver).

**Why MCP here:**

- **Fewer integrations.** Without a standard, 4 systems × several agents × 2 models means many custom wirings. With MCP you build 4 servers, and any MCP-capable model or agent can use them.
- **Model swapping.** The same servers work with Claude or a local model, which the overview's fallback design needs.
- **Discovery and typing.** Agents see which tools exist and what arguments they take, which reduces malformed calls.

**What MCP does not do (the overview overclaims "replaces custom API glue"):**

- The glue moves **inside** the servers: Empower Toolkit calls, SAP OData queries, LIMS SQL. That is still most of the integration effort.
- It does nothing for data meaning: units, synonyms, site-specific field names.
- It widens the attack surface. A document returned by a tool can carry hidden instructions (prompt injection). Mitigations: read-only tools, least-privilege service accounts, per-user OAuth scopes, an allow-list of tools per agent, and logging every call.
- It is not deterministic by itself. In a GMP setting the data pull for a section should be a **reviewed data manifest** (these studies, these batches, these documents) that tools execute exactly. The model may propose the manifest; a human approves it after a completeness check against an inventory from a second system (the ERP batch list, the stability protocol, the study list), so the approver also sees what was left out.

**Alternatives, and why not (or why also):**

| Option | Strength | Weakness | Verdict |
| --- | --- | --- | --- |
| Custom REST adapter per system | Full control | Each agent and model needs its own wiring; no discovery | MCP servers are exactly these adapters with a standard front |
| RPA screen-scraping | Works when there is no API | Fragile, hard to validate | Last resort for UI-only systems |
| ETL / iPaaS (MuleSoft, Informatica) into a data lake | Enterprise-grade bulk sync | Built to move data, not for on-demand agent calls | Good **complement**: ETL loads staging, and checked rows fill the fact store in bulk; MCP serves agents on demand |
| Lab-data platform (TetraScience) | Already connects Empower and LIMS, outputs JSON | Cost, vendor lock-in | Strong "buy" option for the Empower connector |
| One vendor's function calling | Simple | Locks you to one model API | MCP is the vendor-neutral layer over it |

**Check:** the Milestone 1 exit criterion, "retrieval in under 500 ms", measures the wrong thing. Enterprise LIMS and CDS queries often take seconds, and speed is not the risk. A better criterion: every record of a reference study is retrieved, with record counts and checksums matching a manual export.

**Fix:** make completeness the exit criterion. For each reference study, record counts and checksums must match a manual export, with no missing or duplicate records. ALCOA asks for complete data ([FDA, 2018](https://www.fda.gov/media/119267/download)). Speed stays a secondary target: measured, never the gate.

## 12. Document parsing: the vision-language pipeline

Use a vision-language model (VLM) to **understand** a scanned table, but never trust it alone for the digits or the coordinates. Pair it with a layout-aware OCR engine and accept a value only when both agree.

**Rule zero: prefer data over pixels.** If a value exists in LIMS or Empower, take it from there, then compare it with the signed PDF wherever one exists. A mismatch goes to the review queue; a value with no PDF stays unverified. Parse PDFs only for what exists only as PDF: CMO Certificates of Analysis, legacy reports, scanned batch records.

**Check:** the overview has the VLM read peak areas off chromatogram **charts**. That is the wrong source. Empower already stores the integrated peak areas as numbers, and a CMO's chromatogram report prints them in a results table under the curve. Extract the table. A VLM looking at the curve can help as a sanity check ("the table lists 6 peaks, the chart shows 6"), never as the source of a reported value.

**Fix:** take peak results from Empower itself. An Empower Export Method writes the results table, with Result ID, sample name and injection, to a file a connector reads ([Waters](https://support.waters.com/KB_Inf/Empower_Tips_of_the_Week/WKB193142_Exporting_Data_Results_and_Reports_with_Export_Methods_in_Empower)). For CMO PDFs, extract the printed results table. The VLM only counts peaks as a sanity check.

**Two kinds of PDF need different handling:**

- **Born-digital** (exported from software): the text and exact coordinates are already inside the file. Libraries such as pdfplumber or PyMuPDF read them deterministically. No AI needed for the digits.
- **Scanned** (a photo of paper): only pixels. This is where OCR and VLMs come in.

**The recommended pipeline for scans:**

1. **Classify** the document (CoA, batch record, stability report) and check scan quality (resolution, skew).
2. **Layout + OCR**: find tables, headers and footnotes, and read every word with its box on the page. Tools: Docling (open source, runs locally), Azure Document Intelligence, AWS Textract, Google Document AI.
3. **VLM interpretation**: the model reads the page image, and then each table cell, without the OCR words in its prompt, and outputs structured JSON. It decides which column is Month 12, that a footnote says results are in µg/mg, that "Related Substance A" is the known impurity 1. Each value comes with its row and column headers, and the system ties it to the cell box from the detected table grid.
4. **Normalize**: units (a units library such as pint), scientific notation, and special results such as "<0.05%" (below reporting threshold), "ND" (not detected), "NMT" (not more than), "Complies".
5. **Cross-check**: two independent reads of the same cell (the blind VLM read and the OCR read) must agree after typed parsing, and the value must pass its column's rules. VLM says 0.11 but the OCR in that cell reads 0.14? Flag it. The first version of this step compared the OCR with itself; the stress test below shows the flaw and tests the fix.
6. **Route**: a disagreement, a broken rule, or a table that does not match its expected shape goes to a zoom re-read, then to a person.

**Why a VLM at all, and not just OCR?** OCR returns characters. It does not know that a table continues on the next page, that a merged header spans three columns, or that a footnote changes the unit. VLMs handle that layout meaning well.

**Why not a VLM alone?** VLMs can misread a digit in a poor scan, and they are imprecise at pixel coordinates. Asking a VLM for bounding boxes (the overview's `[ymin, xmin, ymax, xmax]` format) gives approximate boxes. For audit-grade provenance, the box must come from the OCR layer or the detected table grid, and an independent read must agree with the value.

| Tool | Type | Good at | Weak at |
| --- | --- | --- | --- |
| pdfplumber, PyMuPDF | Digital-PDF readers | Exact text and coordinates, free, deterministic | Scans |
| Tesseract | Classic OCR | Free, local | Tables, symbols |
| Docling | Open-source layout + table model | Table structure, runs inside a locked-down VPC | Very poor scans |
| Azure DI, Textract, Document AI | Managed layout OCR | Strong tables with coordinates | Cloud dependency |
| Claude, Gemini, GPT (vision); Qwen-VL (local) | VLMs | Layout meaning, footnotes, synonyms | Exact digits in bad scans, pixel boxes |

**On chemical structures:** the overview lists "non-standard chemical structures" as a parsing target. Structure drawings in Module 3 are produced by the sponsor and already exist as structure files in the ELN or compound registry, so there is rarely a need to read them from images. Since drawings usually have a structure file, no model is needed for them. An open optical structure-recognition model (MolScribe) was tested on the finerenone drawing from its FDA label and dropped. It read the drawing as a different molecule, C26H39N3O3 instead of C21H22N4O3, and its 0.83 confidence did not flag the error. So a scanned drawing with no structure file goes to a person. RDKit still computes the formula and weight from registry structures and compares them with the stated values. General VLMs are not a substitute, since they are unreliable at turning a drawing into an exact molecule.

**Check:** ">99.5% extraction accuracy on 2,000 documents" needs a definition. At field level, a CoA with 200 values would still average one error per document, so humans must verify anyway. The metric that matters is **zero undetected errors**: every wrong extraction was flagged by the cross-check or caught in review. Measure how well the flagging catches errors (its recall), not raw accuracy.

**Fix:** replace the accuracy claim with two measured numbers. Seed known errors into a held-out document set, then report how many the flagging caught (target: all) and how many correct values it flagged by mistake (reviewer workload). Write down the context of use, as FDA's [draft AI credibility guidance](https://www.fda.gov/media/184830/download) (January 2025) asks.

### Stress test: the flaw in the cross-check, and the fix

**The flaw in one line.** In the first design, the VLM is shown the OCR words and points to one of them, and the value that gets stored is that OCR word. When the VLM simply repeats the text it was handed, the “cross-check” compares the OCR with itself. On clean PDFs the OCR rarely errs, so the problem stays hidden; on real scans its misreads pass silently, which is exactly when a team discovers it, halfway through a build.

**Five ways the first check breaks:**

| Failure | Why it happens | What you see midway |
| --- | --- | --- |
| Circular agreement | The VLM sees the OCR text in its prompt and tends to repeat it, and the stored value is the OCR word either way | OCR misreads pass silently, and almost nothing reaches a reviewer |
| Wrong-cell binding | The check compares digits, not position. A VLM that slips one row reads the neighbour's value and points to the neighbour's word, so the two agree | A correct number attached to the wrong batch or time point |
| Formatting conflicts | Exact text matching treats “0.11%” vs “0.11”, “0:05” vs “0.05” or a stray speck as a disagreement | Reviewers drown in false alarms as scan quality drops |
| Shared blind spots | Two readers can lose the same decimal point on the same blurred pixels | Both say “858” for 85.8, and their agreement proves nothing |
| Rules that are false on real data | “Each impurity is at most the total” sounds safe, but fails on 20 of the 1,005 real Lek batches | The checker itself raises false alarms |

&#91;embedded content: OCR + VLM cross-check · before and after\]

**How it was tested:**

- **Real values:** 400 batches drawn from the Lek dataset (section 36), printed as 40 certificate-style tables of 10 batches × 6 results: dissolution mean and minimum, impurities O and L, total impurities, residual solvent.
- **Four scan qualities, 2,400 values each (9,600 in all):** a clean digital PDF at 300 dpi; a good scan at 200 dpi with slight blur, noise and up to 0.4° skew; a poor scan at 150 dpi with more blur and noise, heavy JPEG compression, specks and up to 1° skew; a fax or photocopy at 150 dpi in black and white with specks and up to 1.5° skew. The fax setting has milder blur and compression than the poor scan, so it reads more cleanly; it is not the worst case.
- **Two real OCR engines from different families:** Tesseract 5.3 as the page OCR, and PP-OCR (PaddleOCR's models, run through RapidOCR) reading each cell crop. PP-OCR stands in for the VLM's own reading of the image.
- **What could not be measured:** no VLM was called, so how often a VLM repeats the OCR text it is shown was varied from 0% to 100%. Row slips were injected into the naive design's VLM at a rate of 2% (50 per scan quality). They were not injected into the fixed design, which takes position from the table grid; what was measured there is whether the grid and headers were found correctly.

**Results** (counts out of 2,400 values per scan quality):

| Scan quality | OCR misreads | Naive A: wrong values stored | Naive A: sent to a person | Naive B: wrong values stored | Naive B: sent to a person | Fixed: wrong values stored | Fixed: sent to a person |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Clean digital PDF (300 dpi) | 0 | 45 | 0% | 45 | 0% | 0 | 0% |
| Good scan (200 dpi) | 5 | 45 | 0.2% | 45 | 0.2% | 0 | 0% |
| Poor scan (150 dpi, blur, specks) | 125 | 84 | 3.5% | 37 | 11.5% | 0 | 6.0% |
| Fax or photocopy (150 dpi, black and white) | 230 | 170 | 4.1% | 36 | 22.8% | 0 | 2.1% |

Naive A: the VLM repeats the OCR text it was shown. Naive B: the VLM reads independently. Wrong values stored in the naive designs include 35 to 45 row slips per scan quality.

**What the numbers show:**

- **Row slips got through the naive check.** All 50 injected slips passed at clean and good quality, and 45 of them stored a wrong value (in the other 5, the neighbouring row held the same number). On worse scans 35 to 44 wrong values still got through; the rest were flagged only because the OCR also misread the neighbour's value. The fixed design takes position from the table grid, so this failure cannot occur there.
- **If the VLM repeats the OCR, misreads become facts.** On poor scans 40 OCR misreads were stored as facts, and on fax pages 126, while only 3.5% and 4.1% of values reached a person. These counts leave out misreads that are not numbers at all, such as “0:05”, because any number parser would stop them.
- **If the VLM is fully independent, people drown instead.** 11.5% of poor-scan values and 22.8% of fax values went to a person; 117 and 153 of them were correct values that differed only in formatting.
- **Agreement is not proof.** The two engines produced exactly the same wrong text 20 times. 18 were a colon read for the decimal point, which typed parsing turns into the right value. The other 2 were real shared errors, lost decimal points (“858” for 85.8, “915” for 91.5). In the fixed design the column rules sent “858” to a person, and the “915” cell was read correctly from the fixed design's own crops.
- **The fixed design stored zero wrong values.** It accepted 9,406 of the 9,600 values automatically, all correct, and sent the other 194 to a person: none at clean and good quality, 6.0% of poor-scan values and 2.1% of fax values, each with both reads and the cell image side by side. The 263 values it rescued by re-reading were all correct.
- **Diversity matters, on small numbers.** On a 600-value poor-scan sample, Tesseract's page read and its own cell-crop read shared the same wrong answer 4 times; Tesseract and PP-OCR never did (on the fax sample, once each). The counts are small, but they point the same way as the reason for using engines from different families.

**The fixed cross-check:**

1. **Blind reads.** The VLM (or a second OCR engine) reads each cell image without seeing the OCR text, and the two reads never see each other.
2. **Position from geometry.** Deskew the page, detect the ruled grid, and tie each value to a row and column by its cell box. Each column header must read as its expected name; if the grid or headers do not match the expected table, the whole table goes to a person. In the test the grid and headers were found in all 160 tables. The check reads only the first header line, so the two dissolution columns are told apart by position.
3. **Typed, column-aware parsing.** Both reads become a number with its qualifier (“<”) and decimal places. Only noise is cleaned: a colon read for a decimal point, stray specks, letters stuck to the number. Digits are never added or moved, so a lost decimal point still causes a disagreement, and a number that lost a digit fails the range rule.
4. **Column rules, checked against real data first.** Decimal places must match the specification's reporting precision, the value must sit within the historical range, and the dissolution minimum must not exceed the mean.
5. **A second chance only on disagreement.** Re-read the cell at 3× zoom with digits-only settings, using both engine families, and accept only a value agreed by both families that passes the rules.
6. **Everything else goes to a person**, with the cell image and both reads side by side.
7. **Keep measuring in production.** Audit a random sample of auto-accepted values, re-run this stress test with seeded errors on every model or prompt change, and track “both readers wrong in the same way” as the key metric. Before using a VLM as the blind reader, measure its error rate on seeded cells, and check that no OCR text reaches its prompt.

Rule zero still beats all of this: when the same value exists in LIMS, the scan must match it.

**Limits of this test.** No VLM was called; PP-OCR stood in for the VLM's reading, and the VLM's habit of repeating OCR text was varied rather than measured. The tables were rendered from real values, so they are cleaner than many real CoAs, with no merged cells, stamps, handwriting or tables that run across pages; real supplier CoAs should be added next. The blind reads were made on cell crops cut from the grid; the VLM's page-level reading of headers and footnotes was not tested. In the test, decimal places came from the printed table format and the plausible ranges from all 1,005 batches, including the tested ones; in production both come from the approved specification and from earlier batches only. The 2% row-slip rate is an assumption, and zero silent errors among 9,406 auto-accepted values is strong evidence, not proof.

**Run it yourself.** The simulation is about 600 lines of Python (OpenCV, Tesseract, RapidOCR) and runs in about 22 minutes on two CPU cores. The code, results and a README are in the project's ocr\_stress\_test folder.

The same kind of flaw, a check that cannot fail, turned up in ten other places in this design. Section 30 lists them, proposes a fix for each and runs three tests on real data.

## 13. Knowledge layer: Neo4j + Pinecone + BM25

The system asks three different kinds of questions, and each needs a different kind of index. That is the real justification for "hybrid". The overview's specific products, though, clash with its own security design.

**The write gate: nothing reaches the knowledge layer unchecked.** Structured rows and scanned values both land first in a staging area. The gate checks each one before it is stored. A failed row waits in quarantine with its reason, instead of being dropped. A checked fact enters the knowledge layer as one versioned batch, hashed into the ledger, so a bad load can be rolled back.

The knowledge layer is the heart of the system, so it has more than one check:

- **Schema contract.** A row without its batch, test, unit or source ID is rejected, never guessed.
- **Fixed unit rules.** Units convert by a rule table, never by a model. Out-of-range values go to a person.
- **Agreement across sources.** The same fact from LIMS, Empower and the signed PDF must match. A copy never counts as a second source.
- **Drift check.** A scheduled re-read of the sources compares them with the store. Any difference opens a review item.
- **Gate tests.** Before each change to the gate, planted errors (wrong batch, decimal shift, copied value) must still be caught.
- **Read-only consumers.** Statistics, writers and the validator read only from the store, never from staging.

| Question type | Example | Best index | Why |
| --- | --- | --- | --- |
| Relational, multi-hop | "All batches made at Site B with buffer lot X that were out of trend for dissolution" | Graph (or SQL joins) | Follows links: batch → site, batch → material lot, result → test |
| Meaning | "What does ICH say about qualifying a degradation product above threshold?" | Dense vectors (embeddings) | Finds passages with the same meaning in different words |
| Exact term | "Q3B", "AM-102", "ST-2024-9901" | Keyword search (BM25) | Embeddings blur codes and IDs; keywords match them exactly |

**The graph, concretely.** Things become nodes, relationships become edges:

```
(Product)-[:HAS_BATCH]->(Batch)-[:MADE_AT]->(Site)
(Batch)-[:USED_LOT]->(MaterialLot)
(Result)-[:FOR_BATCH]->(Batch)
(Result)-[:OF_TEST]->(Test)-[:USES_METHOD]->(Method {version})
(Result)-[:AT]->(Condition {temp, rh}), (Result)-[:AT_MONTH]->(Timepoint)
(Result)-[:EXTRACTED_FROM]->(SourceLocation {doc, page, bbox})
(Section {id:'3.2.P.5.4'})-[:CITES]->(Result)
(Impurity)-[:SYNONYM_OF]->(Impurity)
```

The relational question above becomes one Cypher query:

```
MATCH (b:Batch)-[:MADE_AT]->(:Site {name:'Site B'}),
      (b)-[:USED_LOT]->(:MaterialLot {id:'BUF-X'}),
      (r:Result {oot:true})-[:FOR_BATCH]->(b),
      (r)-[:OF_TEST]->(:Test {name:'Dissolution'})
RETURN b.id, r.value, r.month
```

**Where a graph earns its place:** batch genealogy (which drug-substance batch went into which drug-product batch), synonym resolution, and impact analysis ("method AM-102 changed to version 4: which dossier sections cite results from version 3?"). That last one is what powers the post-approval future scope.

**Honest counterpoint.** The numbers themselves are perfectly tabular: batch, test, condition, month, value. A relational table handles them more simply, with exact types, constraints and transactions. PostgreSQL, already in the stack for the audit ledger, can also do vector search (pgvector) and full-text search. Version 1 makes the graph the primary store, for lineage queries and the visual. PostgreSQL is the backup, filled from the same write gate, so the two cannot drift apart. It takes over if the graph fails or needs recovery.

**Check: "Graph RAG" means two different things.** Microsoft's GraphRAG (2024) has an LLM extract entities and relationships from free text. This project's graph should be built from **structured source data** by deterministic code. Never let an LLM invent edges between GMP facts.

**Fix:** deterministic code builds every edge from source keys (batch ID, test ID, method ID) and writes it through the write gate. An LLM may propose an edge only into a review queue. Microsoft's [GraphRAG](https://arxiv.org/abs/2404.16130) uses LLM-extracted edges, so cite it as the contrast, not the method.

**How retrieval should work:** a query runs through BM25 and vector search in parallel; results are merged (reciprocal rank fusion), re-scored by a reranker model, and filtered by metadata such as guideline, region and version. Versions matter: the ICH Q1 revision reached Step 2 (public draft) in April 2025 and will supersede Q1A–Q1F and Q5C, so the index must know which text applies to a given filing. Retrieval supplies quotes, never the numbers a check depends on: limits come from the product's approved specification, and guideline thresholds from a rule table keyed on modality, maximum daily dose and guideline version (section 30).

**The real fix for "chunking destroys tables"** is table-aware chunking: keep a table whole, or chunk by row with its column headers repeated. Guidelines are chunked by their own numbered sections. Long context helps, but this is the actual cure.

**Check: three sovereignty contradictions.** The overview promises a single-tenant, isolated AWS GovCloud deployment, then picks:

- **Pinecone Serverless**, a multi-tenant service run in Pinecone's own cloud. Pinecone's BYOC option (generally available, Enterprise plan) puts the data plane in your AWS, GCP or Azure account, but its docs do not list GovCloud.
- **Neo4j Aura**, Neo4j's managed service on commercial clouds. For isolation you would self-host Neo4j Enterprise inside the VPC.
- **OpenAI text-embedding-3-large**, an external API. Every chunk of proprietary text would be sent to a third vendor to be embedded.

| Need | Overview choice | Recommended inside a locked-down VPC |
| --- | --- | --- |
| Fact store (the numbers) | Implicitly Neo4j | PostgreSQL tables |
| Relationships, lineage | Neo4j Aura | Self-hosted Neo4j Enterprise, or Postgres first |
| Meaning search | Pinecone Serverless | pgvector or OpenSearch (millions of chunks is small for either) |
| Keyword search | BM25 via Pinecone sparse vectors | OpenSearch BM25 or Postgres full-text |
| Embeddings | OpenAI text-embedding-3-large | An open embedding model on the project's own GPUs |

**Fix:** keep every part inside the customer's region. The graph runs as Neo4j Enterprise in the customer's VPC; Aura fits only on Business Critical with AWS PrivateLink, still a preview in Ireland, London and Paris ([Neo4j](https://neo4j.com/docs/aura/security/private-endpoints/)). Meaning search uses pgvector in the Postgres backup, which [Amazon RDS supports](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html). Embeddings come from [Titan Text Embeddings V2](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-titan-text-embeddings-v2.html) in the same region, or an open model on the project's GPUs.

## 14. Orchestration: Temporal outside, LangGraph inside

LangGraph is a good choice, but for the right reason: it lets you build a **mostly fixed, auditable state machine** with a few AI steps inside, rather than a crowd of free-roaming agents. In a GMP setting, predictable beats clever.

**What LangGraph is.** A library from the LangChain team for building AI workflows as graphs:

- **Nodes** are steps (a Python function or a model call).
- **Edges** connect them; conditional edges choose the next step from the current state.
- **State** is one typed object that every node reads and updates.
- A **checkpointer** saves the state after every step, so a crashed run resumes where it stopped.
- **Interrupts** pause the graph for a human to review, edit or approve, then resume.

[LangGraph 1.0 became generally available on 22 October 2025](https://www.langchain.com/blog/langchain-langgraph-1dot0), highlighting durable state, built-in persistence and human-in-the-loop, with Uber, LinkedIn and Klarna named as production users. **Check:** the overview's "LangGraph v0.3+" is outdated; target 1.x.

**Fix:** target LangGraph 1.2.x; 1.2.16 shipped on 16 October 2026 ([release list](https://releases.sh/langchain/langgraph-releases.md)). Pin the exact version in the lockfile. Version 1.1 added an opt-in "v2" output format; adopt it in one planned change with regression tests, not mid-build.

**Workflow vs agent.** A workflow follows paths you wrote in code; an agent lets the model decide the next step. This pipeline is mostly a workflow: ingest → parse → stage → validate → promote to fact store → compute → retrieve rules → draft → check → human review → sign. Model freedom belongs only inside bounded steps, such as interpreting an odd CoA layout or phrasing a paragraph. The "supervisor" should therefore be mostly routing code with a model consulted for exceptions, not a model improvising the whole run.

**Two layers: Temporal outside, LangGraph inside.** One submission section takes weeks: data pulls fail and must retry, and sign-offs wait for days. LangGraph saves checkpoints, but a run lives in one process, and something must restart it after a crash ([Temporal, July 2026](https://temporal.io/blog/temporal-langgraph-plugin-durable-execution)). So a Temporal workflow runs the pipeline above, one activity per step. It waits durably for each signature, with a timer that escalates a stalled review. LangGraph runs only inside the steps that need a model: parsing odd layouts, drafting and explaining.

- **Retries:** Temporal retries timeouts and connector errors. A failed verification is raised as a non-retryable error, so it goes to a person, not into a retry loop.
- **Not the audit trail:** Temporal Cloud keeps a closed workflow's history for 1 to 90 days, and one run holds at most 51,200 events or 50 MB ([limits](https://docs.temporal.io/cloud/limits)). The hash-chained ledger stays the GxP record, and each section runs as its own workflow.
- **Inside the boundary:** self-host Temporal in the customer's VPC, so workflow inputs never leave the region.
- **Change control:** workflow code changes are versioned, so a submission already running finishes on the code it started with.
- **The plugin:** Temporal's LangGraph plugin runs each node as an activity, but it is a public preview ([docs](https://docs.temporal.io/develop/python/integrations/langgraph)). Until it is stable, call a LangGraph graph from inside one activity, with its Postgres checkpointer.
- **Why not Airflow or Prefect:** Airflow schedules batch DAGs, and long waits hold its worker slots ([comparison](https://automationatlas.io/guides/temporal-vs-apache-airflow-2026-comparison/)), so it suits nightly syncs, not week-long sign-offs. Prefect could work, but Temporal's durable waits and versioning fit this pipeline best.
- **Student build:** write each step as a plain function from day one. Wrap the steps in Temporal, which is open source and runs locally, once the first human wait or cross-system retry appears. It is then a wrapper, not a rewrite.

**The agents, judged:**

| Agent | Job | Should be | Comment |
| --- | --- | --- | --- |
| Ingestion | Fetch data via MCP | Deterministic | Executes the human-approved data manifest (section 11) |
| VLM Parser | Turn scans into facts | Model + deterministic cross-check | Section 12 |
| Mathematical Verification | Statistics and table-math checks | Deterministic code | The model may pick which validated function to call, never compute or type values |
| Regulatory Compliance | Compare results with specs and ICH thresholds; retrieve and explain guidance; check section completeness against M4Q | Rules for comparisons, model for retrieval and explanation | "0.11% vs limit 0.2%" is a code comparison, not a model judgment |
| Compliance Audit | Record every step | Not an agent | Logging must be automatic at framework level (callbacks on every node and tool call). An agent that decides what to log is a compliance hole |
| Redaction (short overview only) | "PII / HIPAA filter" | Rules + model | **Check:** HIPAA protects patients' health information, which CMC data almost never contains. What CMC files do contain is employee names and signatures in batch records and CMO trade secrets. Reframe as confidentiality redaction |
| **Missing:** Writer | Draft prose with fact placeholders | Model | The overview folds this into the supervisor; it deserves its own node |
| **Missing:** Consistency Checker | Same value identical in 3.2.S, 3.2.P and Module 2.3; text claims match tables | Deterministic | The single biggest error source in section 3, yet no agent owns it |

**Fix (redaction row):** classify what CMC files really hold. Trade secrets and confidential commercial information are protected from public disclosure under [21 CFR 20.61](https://www.law.cornell.edu/cfr/text/21/20.61), so tag them at ingest. Staff names and signatures are personal data, and GDPR applies to EU staff, so mask them in any output that leaves the GMP record. CMO data follows each supply contract's access rules.

**Why Temporal and LangGraph, and not the alternatives:**

| Option | What it is | Fit here |
| --- | --- | --- |
| **LangGraph** | Graph state machine with checkpoints and interrupts | Explicit control flow, resumable, human-in-the-loop built in. Downside: a fast-moving ecosystem with extra abstraction |
| CrewAI | Role-based agent teams | Built around autonomous collaboration; control flow is less explicit, so harder to validate |
| AutoGen-style chat agents | Agents converse to solve a task | Conversation paths vary run to run; poor for validation |
| Temporal, Airflow, Prefect | Durable workflow engines | **Chosen: Temporal for the outer pipeline**, with LangGraph inside the model steps. Airflow suits scheduled batch jobs, not week-long human waits |
| Plain Python + a task queue | Your own code | Maximum control, but you rebuild checkpointing and human pauses yourself |
| Vendor agent SDKs (Claude Agent SDK, OpenAI Agents SDK) | One vendor's agent toolkit | Tied to one model provider; fine for sub-tasks |

**Two design corrections:**

- **Checkpoints in Postgres, not Redis.** The overview checkpoints to Redis, an in-memory store. For a regulated audit trail, checkpoint to Postgres (LangGraph supports it), and hash each checkpoint into the ledger.
- **Retry only transient failures.** "Automated error recovery loops" are fine for timeouts. They are dangerous for failed verifications: retrying until the checker passes finds output that satisfies the checker, not output that is true. A failed number check goes to a human.

## 15. Models: one pick per task, and where each runs

A strong frontier model for interpretation and writing plus a local open model for sovereignty is a sound pattern. The specific pairing in the overview has three problems: the cloud model cannot run inside the promised GovCloud boundary, R1 cannot see images, and both picks are already a generation old.

**Decision (October 2026): rent frontier models for the thinking, and self-host only the small parts.** Claude Opus 5.5 leads the [Artificial Analysis index](https://artificialanalysis.ai/leaderboards/models) at 58, and Sonnet 5.5 scores 56 at half the price. Cheap models are good enough for classification, and retrieval runs on a laptop CPU. The table at the end of this section gives one pick per task; no public benchmark measures regulatory drafting or pharma tables, so a 30–50-item in-house eval makes the final call.

**Why a frontier model like Claude for the main role:** long context (read a whole study report at once), strong reasoning over scientific text, vision for scanned pages, reliable structured output (JSON, tool calls), and high-quality technical writing.

**What Claude Opus 4.6 actually is.** Released 5 February 2026 with a [1M-token context window, in beta at launch](https://www.rdworldonline.com/claude-opus-4-6-targets-research-workflows-with-1m-token-context-window-improved-scientific-reasoning/). Anthropic reported 76% on the MRCR v2 long-context retrieval benchmark versus 18.5% for its predecessor, and large gains on life-science benchmarks (self-reported). It is still active, with retirement [not before 5 February 2027](https://platform.claude.com/docs/en/about-claude/model-deprecations).

**It is no longer the newest.** As of September 2026 Anthropic's [current models](https://platform.claude.com/docs/en/models/overview) are Claude Opus 5.5 and Sonnet 5.5 (1M context; $4 / $20 and $2 / $10 per million input / output tokens) and Claude Fable 5.1 for the hardest reasoning. The lesson is not "switch to 5.5" but **never hard-wire a model**: pin an exact model ID per validated release, log it on every call, and re-validate before changing it. Anthropic gives at least 60 days' notice before retiring a model.

**Check: the GovCloud contradiction.** AWS's [FedRAMP list for Bedrock models](https://aws.amazon.com/compliance/services-in-scope/FedRAMP/amazon-bedrock-models/) shows Claude 4.5 Opus authorized in GovCloud, but not Opus 4.6. So "Claude Opus 4.6 (Cloud)" inside a GovCloud single-tenant VPC would mean calling a public API outside the boundary, which breaks the overview's own sovereignty promise.

**Fix:** run Claude through Amazon Bedrock in the customer's commercial region, using a model AWS lists there. Claude Opus, Sonnet and Haiku 5.5 all have Bedrock EU inference profiles that keep processing inside the EU ([AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html)). Anthropic's own API offers only US or global inference, not EU ([Anthropic](https://platform.claude.com/docs/en/manage-claude/data-residency)). Pin the model version.

**What DeepSeek-R1 actually is.** An open-weights reasoning model released January 2025 under the MIT license: 671B total parameters (mixture-of-experts, about 37B active per token), **text only**. Three problems:

- **It cannot see.** The challenges table says the local model does "preliminary data parsing". Parsing scans needs vision; R1 has none.
- **It is heavy.** About 700 GB of weights at FP8 is more than one 8×H100 node holds (8 × 80 GB = 640 GB), so full R1 needs multiple nodes. The small "distilled" R1 versions fit easily but are much weaker.
- **It is outdated and politically awkward.** [DeepSeek V4](https://api-docs.deepseek.com/news/news260424/) shipped 24 April 2026 (1.6T parameters, 1M context). At least 15 US states [banned the DeepSeek app on government devices](https://statetechmagazine.com/article/2025/04/these-states-have-banned-deepseek) in 2025. Open weights run locally send nothing to China, but many pharma security reviews flag Chinese-origin models, and a GovCloud pitch makes that worse.

**Local alternatives (October 2026):** Google's Gemma 4 is the best open family that passes a typical pharma security review: Apache 2.0, with 31B for drafting and vision and 26B-A4B for fast classification ([Gemma 4 report](https://arxiv.org/pdf/2607.02770)). IBM Granite 4.1 and Mistral (Apache 2.0) are alternatives; gpt-oss (August 2025) is now dated. The strongest open models (Qwen3.8, DeepSeek V4.1, GLM-5.3, MiMo) are Chinese-origin, and even so the gap is large: Gemma 4 31B scores 15 on [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models) against 58 for Opus 5.5.

**Check: long context does not replace retrieval.** 1M tokens is roughly 750,000 words, on the order of 1,500 to 3,000 pages of dense text, and page **images** cost more tokens than text. The overview's 50,000-page ingestion cannot fit. Use long context to read one whole report or one section's evidence at once; use the fact store and retrieval for everything else. Cost also scales: at $4 per million input tokens, one full 1M-token call costs about $4 in input alone before caching.

**Fix:** retrieval first. The fact store, graph and search pick the evidence; the model reads one report or one section's evidence pack at a time, under a set token budget per call. Cache repeated evidence, and log tokens per call so cost stays visible.

**Check: "fallback" is risky in a validated system.** Switching silently to a different model when the primary is down produces different outputs. Each model configuration must be validated for its job; a switch is a controlled, logged event.

**Fix:** no silent fallback. If the validated model is down, the job pauses in a queue. A second model is allowed only if it was validated for the same task beforehand, and the switch is logged with every output. The EU's draft [Annex 22](https://health.ec.europa.eu/consultations/stakeholders-consultation-eudralex-volume-4-good-manufacturing-practice-guidelines-chapter-4-annex_en) (consultation closed 7 October 2025) expects change control and ongoing oversight of AI. A [summary of the draft](https://sakaradigital.com/blog/ema-annex-22-implementation-timeline-may-2026/) says it keeps LLMs out of critical GMP functions, so LLM output stays behind code checks and human sign-off.

**Recommended model per task (October 2026; prices per million input / output tokens):**

| Task | Best pick | Cheaper, good enough | Student build | Sovereign or offline |
| --- | --- | --- | --- | --- |
| Numbers, statistics, comparisons | No model: validated code (section 16) | Same | Same | Same |
| Scientific drafting with fact placeholders | Claude Opus 5.5 ($4 / $20) | Claude Sonnet 5.5 or GPT-6.1 Sol ($2 / $10) | Gemma 4 E4B on the laptop, Gemma 4 26B on Kaggle ($0) | Gemma 4 31B |
| Scan read 1: OCR, source of cell coordinates | AWS Textract Tables ($15 per 1,000 pages) | Azure Document Intelligence Layout (about $10 per 1,000) | Docling on the laptop CPU | Docling (MIT) |
| Scan read 2: independent vision read | Gemini 3.8 Flash (about $6 per 1,000 pages, estimated) | Claude Haiku 5.5 (about $1 per 1,000, estimated) | Gemma 4 on Kaggle ($0) | Gemma 4 31B |
| Classification, routing, extraction QA | Claude Haiku 5.5 ($0.10 / $0.50) | GPT-6 Luna (same price) | Gemma 4 E4B on the laptop ($0) | Gemma 4 26B-A4B |
| Guidance retrieval | BM25 + EmbeddingGemma 2 + mxbai-rerank-v2, run locally; Sonnet 5.5 writes the answer | EmbeddingGemma v1 (308M) | Same retriever on the laptop | Same retriever; Gemma 4 writes the answer |
| GEPA prompt tuning (reflection) | Claude Opus 5.5 | Sonnet 5.5 | Gemma 4 26B on Kaggle ($0) | Tuned in the cloud on public data; prompts shipped to the box |

**Where each model runs.** The laptop holds only the plumbing: the validator, Docling, BM25, EmbeddingGemma and the reranker, a few GB in all. A small Gemma 4 E2B or E4B (4–6 GB) is enough for offline tests; drafting never runs on a laptop, because a CPU manages only about 3–10 tokens a second. In the student build, drafting and vision run on Gemma 4, on the laptop or on Kaggle. APIs are optional and take public documents only; the Gemini free tier is one, but Google uses free-tier data outside the EEA, UK and Switzerland ([Gemini API terms](https://ai.google.dev/terms)).

In production every call stays in the customer's region. Claude goes through Bedrock `eu.` or `us.` profiles, because Anthropic's own API has no EU option ([Anthropic](https://platform.claude.com/docs/en/manage-claude/data-residency)); Textract runs in-region, and Gemini goes through Google Cloud's `eu` endpoint. Batch is excluded from zero-retention terms, so confidential dossiers save money with prompt caching, not batch ([Anthropic](https://platform.claude.com/docs/en/build-with-claude/zero-data-retention)).

**Local or online: which is cheaper?** Online, at every volume this project will see. Self-hosting means renting a GPU server, and an idle GPU still bills by the hour.

| Option | Monthly cost |
| --- | --- |
| Student build: Gemma 4 on the laptop and Kaggle, or APIs with Sonnet 5.5 (about 10 sections a month) | $0, or about $15–27 on APIs |
| One L4 GPU server left on | about $416–588 |
| One L40S GPU for sovereign mode (AWS) | about $1,360 |
| One H100 on AWS on-demand ($6.88 an hour) | about $5,000, never cheaper than open-model APIs |

A dedicated H100 serving gpt-oss-120b matches the API price of about $0.20 per million tokens only at 39–62% sustained use on specialist clouds, roughly 150–240 Module 3 dossiers a month ([SemiAnalysis](https://inferencex.semianalysis.com/run/gptoss-120b-on-h100); [Together](https://www.together.ai/pricing)). At ten customers drafting two dossiers a month it sits about 5% used and costs $2.47–4.26 per million tokens, about what Sonnet 5.5 costs, for a far weaker model. Self-hosting wins only for embeddings (free on the app server's CPU), very high OCR volume (above about 39,000 pages a month against Textract) and sovereign mode, which the customer pays for as data control.

The token volumes behind these figures are an estimate (0.5–1M tokens per Module 3 section), not a measurement. Gemini 3.8 Flash's price doubles on 1 January 2027 ([Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)).

**The $0 student build: a free local writer, held up by checks.** On a 16 GB laptop the writer is Gemma 4 E4B through Ollama; bigger runs use Gemma 4 26B on Kaggle's free GPUs (about 30 hours a week). Quality comes from the pipeline around the model, not from its size:

1. Code computes every number and every judgement (trend, compliance) and gives each an ID.
2. Code writes the fixed sentences and the table. The model writes only a 2–4 sentence discussion, with a `[[placeholder]]` for every value.
3. The validator rejects any draft with a raw number, an unknown placeholder, a wrong trend word or a hidden out-of-specification result.
4. The model writes one draft, and more only when the validator rejects it, up to four.
5. Code inserts the values, and a person signs.

The research supports each part, but no paper tests this exact combination for regulatory drafting. A small model given extra drafts and a checker can beat a model 14 times its size on problems it already solves sometimes ([Snell et al.](https://arxiv.org/abs/2408.03314)). Resampling one model beats mixing several ([Self-MoA](https://arxiv.org/abs/2502.00674)). When table statements are checked by code, smaller models still make more errors (GPT-OSS 20B 87.3% correct against 93.8% for 120B), so here they cost extra drafts, not wrong text ([STAT-TO-TEXT](https://arxiv.org/pdf/2609.23966)).

The `writer_test` harness tests this on eight synthetic stability sections. It reports how often the first draft passes, drafts per section and minutes per section, and runs a blind comparison against Claude. The pipeline counts as feasible if at least 7 of 8 sections pass within four drafts, at under about 3 minutes a section on the laptop.

**Result (27 October 2026):** on the 16 GB laptop, Gemma 4 E4B passed all 8 sections within four drafts, at about 11 seconds a section (1.4 minutes for the whole run). 7 passed on the first draft, counted after fixing a validator rule that had wrongly rejected one correct draft. No paragraph had a wrong number, batch or month. The failed drafts broke wording rules, such as writing a number as a word. Gemma 4 26B on a free Kaggle T4 took about 3 seconds a section, but that run used an older prompt and is being repeated. This proves the method on one short, templated section type only. In a blind rating of 5 sections against Claude (one rater, scores out of 5), the two came out about even: writing 4.0 for Gemma vs 3.6 for Claude, judgement 3.8 vs 4.2. The prompt is so tight that both models write almost the same template, so this task cannot tell them apart. Harder sections, where the model has to choose what to say, are the next test.

## 16. Math sandbox: code, not model arithmetic

Moving math out of the model and into code is the overview's best idea. But the stronger version is a **pre-validated statistics library** the model can only call, not a sandbox where the model writes fresh code for every request.

**Why code at all.** A model predicts the next token. It is usually right at arithmetic, and "usually" cannot be validated. Code gives the same answer every time, can be unit-tested, and can be re-run by an inspector years later.

**Check: "PyChain WASM" does not exist.** No product or library by that name turns up. The overview most likely means "Python running inside a WebAssembly sandbox inside Docker". Real options:

| Sandbox | What it is | Trade-off |
| --- | --- | --- |
| Pyodide | CPython compiled to WebAssembly; runs NumPy, pandas, SciPy | Strong isolation, slower, some packages missing |
| gVisor, nsjail | Kernel-level isolation for ordinary containers | Fast, needs careful configuration |
| Firecracker microVMs (used by services such as E2B) | Tiny virtual machines per run | Strongest isolation, more setup |
| Plain Docker, no network, read-only disk, CPU/memory limits | The common baseline | Weakest of the four, often enough inside a private VPC |

**The better design for GMP work:**

1. Write a **statistics library** once: mean, standard deviation, %RSD, ICH Q1E regression and poolability, shelf-life estimation, out-of-trend tests, specification comparisons, regulatory rounding.
2. Unit-test it against reference results and validate it once (risk-based, GAMP 5 style).
3. Expose each function as a tool: `shelf_life(fact_ids, spec_limit)`. The model chooses the function and the fact IDs; it never writes the math or types the values.
4. Keep free code for exploratory, clearly labelled non-GMP analysis only, run in a Firecracker microVM.

**Fix:** drop "PyChain WASM" from the design. GMP numbers come from the validated statistics library above, called as tools with fact IDs. Any free code runs in a **Firecracker microVM**: a tiny virtual machine started for one run, with no network and a read-only disk, then thrown away. Its output is labelled non-GMP. Firecracker gives the strongest isolation of the four options; the cost is setup. It needs Linux with KVM, so it runs on a bare-metal server, on a cloud VM that allows nested virtualisation, or on the Windows laptop inside WSL2 with nested virtualisation turned on. E2B is open source and built on Firecracker, and self-hosting it saves part of that work.

**The statistics that actually apply (explained simply):**

- **Shelf life (ICH Q1E):** fit a straight line of the attribute against time. For an impurity that rises, shelf life is where the **upper one-sided 95% confidence bound** of that line crosses the specification limit (for assay that falls, the lower bound). Batches may be pooled only if their slopes and intercepts do not differ, tested at a significance level of 0.25. Extrapolation beyond the real data is allowed only within limits (roughly up to twice the data period, and no more than 12 months beyond it).
- **Out of trend (OOT):** a result still inside specification but unusual for this product. Standard methods compare the new result with a **prediction interval** built from earlier data or historical batches (regression control chart, by-time-point method, slope control chart).
- **Awkward values:** "<0.05%" (below the quantitation limit) cannot simply be averaged. The library needs a written policy for it.
- **Rounding:** results are rounded to the number of decimals in the specification, rounding a trailing 5 up. **Python's built-in `round()` does not do this**: `round(0.125, 2)` gives 0.12 and `round(2.675, 2)` gives 2.67 (half-to-even rounding plus binary floating point). Use `Decimal` with `ROUND_HALF_UP`, which gives 0.13. A classic silent bug.

**Check: the overview's example script has four flaws.** I ran it on its own data:

1. **Values are typed into the script by the model** (section 6).
2. **Its OOT test is nearly blind.** It fits the line through all points, including the Month-36 value it is testing, then flags OOT only if that value is 0.02 above the line. Because the tested point drags the line toward itself, the test first flags OOT only when the Month-36 value reaches **0.164%**. A proper 95% prediction interval from the earlier points flags anything above about **0.124%**. The fixed 0.02 margin has no statistical basis.
3. **"Mean impurity" across time points is meaningless**: it averages a trend. Useful are the slope, or the mean across batches at one time point.
4. **Formatting to 4 decimals** ignores the specification's reporting precision.

**Fix:** rewrite the script on the library. Values load by fact ID. OOT uses a 95% prediction interval built from earlier time points only. Report the slope, or the mean across batches at one time point. Round to the specification's decimals with `Decimal` and `ROUND_HALF_UP`.

**Check: "100% mathematical accuracy"** is true only of arithmetic. Code removes arithmetic errors; it does not remove wrong inputs, the wrong statistical method or the wrong rounding rule. Likewise "zero calculation errors across 500 matrices" is trivially true for deterministic code. The meaningful test compares outputs with independently validated reference results (for example from JMP or SAS) on hard edge cases: missing time points, "\<LOQ" values, rounding ties, a single batch that cannot be pooled.

**Fix:** claim "validated against reference results" instead. Test the regression code against NIST's [Statistical Reference Datasets](https://www.itl.nist.gov/div898/strd/), which come with certified results, and against JMP or SAS on the edge cases above. The test suite becomes the validation evidence.

## 17. Human review workspace

The review screen is where the project earns trust: click any number in the draft and see the exact source cell, highlighted. Its hardest problem is not the code but **automation bias**: people start rubber-stamping green checkmarks.

**What the screen does:**

- **Left pane:** the draft section in a rich-text editor. Every number is a non-editable "fact chip" carrying its fact ID; a writer cannot type a raw number.
- **Right pane:** the source PDF, rendered with a box drawn over the exact cell when a chip is clicked.
- **Fact panel:** value, source system, extraction route, which checks passed, which calculations used it, and its review state (unverified, verified, rejected with reason).
- **Live progress** of long runs over WebSockets.

**Why a human must sign.** The sponsor is legally responsible for what it submits. Under Part 11 an accountable person signs electronically, and the signature shows their name, the date and time, and its meaning, such as "Approved" (section 18). An AI cannot hold that responsibility. FDA's January 2025 **draft** guidance on AI for regulatory decision-making asks for a risk-based credibility assessment of any AI model for its specific context of use; strong human review lowers the model's influence on the final decision and so lowers the evidence burden. The [FDA–EMA Good AI Practice principles](https://www.jonesday.com/en/insights/2026/01/ema-and-fda-align-on-good-ai-practice-in-drug-development) (14 January 2026, voluntary) stress the same things: human-centric design, a clear context of use, data governance and lifecycle management.

**Designing against rubber-stamping:**

- **Risk-based review.** A value pulled by API from validated LIMS, with a matching checksum, needs a lighter check than a value read from a blurry scan. Machine-read values with any disagreement always need an explicit human check. This is what makes "100% human verification" affordable.
- **Show doubt loudly.** Disagreements, low confidence and "\<LOQ" handling sit at the top, not buried.
- **Blind confirmation and challenge testing.** For high-risk values, the reviewer reads the source cell and enters the value before the system's value is shown, so agreement cannot come from simply accepting it. Seed known errors into each reviewer's queue and track each reviewer's catch rate. In a 2025 online experiment, 2,784 crowdworkers checked AI-extracted values from company report tables. They caught 82% of spelling or digit errors, about 77% of values taken from the wrong cell and only 31% of errors that needed knowledge of the rules ([Beck et al.](https://arxiv.org/abs/2509.08514v1)). That study had no group working without AI suggestions, so it shows how much checkers miss, not that blind entry fixes it; the seeded challenge items are how this design measures that.
- **Attest per table** for high-risk sections, not one click for the whole document.
- **Re-check on every edit.** When a writer changes text, the claim and number validator runs again.

**Technology choices:**

| Piece | Overview pick | Why it fits | Alternatives |
| --- | --- | --- | --- |
| UI framework | React 19 + TypeScript | Largest ecosystem for complex apps; types catch bugs | Angular (common in enterprise pharma), Vue, Svelte: no strong reason to switch |
| Editor | ProseMirror | A toolkit for **structured** documents with custom node types, exactly what fact chips need (Tiptap is built on it) | Lexical, Slate; Quill is too loose for structured content |
| PDF viewer | (unnamed) | PDF.js renders PDFs in the browser and allows overlays | Commercial SDKs such as Apryse |

**Two practical traps:**

- **Coordinate mapping.** OCR boxes are in image pixels; PDF.js draws in PDF points, and pages may be rotated or scaled. A wrong conversion puts the red box on the wrong cell, which destroys trust. Test it on rotated and odd-sized scans.
- **Writers live in Word.** Adoption depends on meeting them there: export to .docx with the fact links preserved as bookmarks or fields, or build a Word add-in. Veeva's announced Agentic Authoring integrates with Word for this reason.

Section 34 shows what this workspace looks like to the writer and reviewer, and the design choices behind it.

## 18. Audit ledger and 21 CFR Part 11

Part 11 requires secure, computer-generated, time-stamped audit trails and properly linked e-signatures. It does **not** require blockchains or hash chains. A hash chain adds tamper-**evidence**, a good extra, and the overview's append-only PostgreSQL with SHA-256 chaining is a sensible, cheap design once three holes are closed.

**What [21 CFR Part 11](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11) asks for, section by section:**

| Section | Requirement in plain words | How this project meets it |
| --- | --- | --- |
| 11.10(a) | The system is validated | GAMP 5-style validation (section 31) |
| 11.10(d) | Only authorized people get access | SSO + role-based permissions (section 19) |
| 11.10(e) | Secure, computer-generated, time-stamped audit trails of who created, changed or deleted what; old values stay visible | The ledger |
| 11.10(k) | Controlled system documentation | Versioned SOPs, specs, change control |
| 11.50 | A signature shows the printed name, date and time, and meaning ("Approved") | Signature records in the ledger and on the rendered PDF |
| 11.70 | Signatures linked to their records so they cannot be cut, copied or moved to falsify another record | The signature record includes the SHA-256 hash of the exact signed document |
| 11.100 / 11.200 / 11.300 | Signatures unique to one person; non-biometric ones need two components (ID + password); password controls | Re-authentication at signing, through the company's identity provider |

**How a hash chain works.** Each entry stores a fingerprint (hash) of itself **plus the previous entry's fingerprint**:

```
h1 = SHA256(h0 + entry1)
h2 = SHA256(h1 + entry2)
h3 = SHA256(h2 + entry3)
```

Change anything in entry 1 and h1 changes, which breaks h2, h3 and every link after it. A verifier recomputes the chain from the start and finds the first break.

**Three holes and their fixes:**

1. **An admin can rewrite the whole chain** by recomputing every hash. Fix: periodically **anchor** the latest hash outside the database, for example in S3 with Object Lock in compliance mode (write-once storage nobody can delete, even an admin) or with an RFC 3161 timestamping service.
2. **"Append-only" must be enforced, not promised.** Fix: the application's database role may INSERT only; no UPDATE or DELETE grants; a trigger rejects updates anyway.
3. **Anyone with insert rights could append forged entries.** Fix: sign each entry (or each batch of entries) with a key held in AWS KMS / an HSM that only the ledger service can use.

**What to log:** every user action (who, what, when, why); every model call (exact model ID, full prompt, parameters, output); every tool call; every data pull (record IDs + checksums); the version (git commit) of the statistics library; every workflow checkpoint; every review decision; every signature with its document hash. Large payloads such as 1M-token prompts go to write-once object storage; the ledger stores their hashes.

**Alternatives, and why not:**

| Option | Status | Verdict |
| --- | --- | --- |
| Amazon QLDB (a managed ledger with built-in hash chains) | **Discontinued: end of support 31 July 2025**; AWS recommended Aurora PostgreSQL, which has audit logging but [no built-in cryptographic verification](https://www.certyos.com/en/blog/aws-qldb-migration-lesson) | Would have been the obvious pick; a reminder that owning the design matters |
| Blockchain (Hyperledger and similar) | Available | Overkill: one organization, no need for distributed consensus |
| immudb | Open-source immutable database | Credible alternative |
| Azure SQL Ledger | Available on Azure | Good if the company runs on Azure |
| PostgreSQL + hash chain + WORM anchoring + signing key | The overview's choice plus fixes | Recommended |

**The European side, which the overview omits.** EU GMP Annex 11 is Europe's counterpart to Part 11, and a revision was published for consultation in July 2025 together with a new **Annex 22 on AI**. Draft Annex 22 [says generative AI and LLMs "should not be used in critical GMP applications"](https://www.pharmtech.com/view/europe-tried-to-ban-generative-ai-from-critical-gmp-the-ban-may-not-survive-it-does-not-matter-); for non-critical uses they are acceptable when qualified people confirm the output. It was still a draft in August 2026, with final text targeted for late 2026. Drafting a submission with a human verifying every number fits the non-critical, human-confirmed pattern. The overview's future idea of an LLM adjusting bioreactors (section 32) collides with it head-on.

## 19. Security, deployment and scale

One isolated environment per customer is exactly right for pharma, which guards formulas and processes as crown jewels. AWS GovCloud is the wrong default: it is built for US government workloads, lags on AI model availability, and would block the European and Japanese expansion the overview plans.

**The gateway layer:**

| Piece | What it does | Why this choice | Notes |
| --- | --- | --- | --- |
| FastAPI | Python web framework serving the app's API | The AI stack is Python (LangGraph, NumPy), so one language end to end; automatic API docs; request validation with Pydantic | It is an app framework, not an "API gateway". A load balancer with a web application firewall (or Kong/Envoy) still sits in front |
| OAuth2 / OIDC, SAML 2.0 via Okta or Microsoft Entra ID (formerly Azure AD) | Single sign-on with the company's own identity system | Pharma will not accept separate passwords; roles come from their directory | Roles: writer, QA reviewer, approver, admin. Re-authenticate at signing (Part 11.200) |
| Redis rate limiter, circuit breaker | Stops the app from flooding LIMS or Empower; trips when a dependency fails | Legacy lab systems fall over under bursts | Reasonable |
| TLS 1.3, FIPS 140-3 key management | Encryption in transit; US-government-validated crypto modules (AWS KMS HSMs) | Required for government work; harmless otherwise | Fine |

**Check: GovCloud.** AWS GovCloud (US) exists for regulated US government data (FedRAMP High, ITAR, defense). For a pharma customer it brings a smaller service catalog, US-persons-only administration, and slower model availability: Claude Opus 4.6, the overview's own primary model, is not on AWS's GovCloud Bedrock list (section 15). Pharma companies normally run GMP systems in commercial cloud regions under a documented shared-responsibility model. A European customer will want an EU region for GDPR. Recommended: a commercial region per customer (US or EU); GovCloud only as an option for government-funded programs.

**Fix:** one commercial AWS region per customer: Frankfurt or Ireland for EU customers, a US region for US customers. Every part runs there, and Bedrock's geographic cross-region inference keeps processing inside the EU or the US ([AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html)). GovCloud is offered only for government-funded programs.

**Check: "FedRAMP High, HIPAA, 21 CFR Part 11 compliant" infrastructure.** No infrastructure is Part 11 compliant by itself. Part 11 compliance is a property of the whole system plus the customer's procedures, and the customer validates it. HIPAA is largely irrelevant to CMC data (section 14).

**Fix:** say "supports the customer's Part 11 compliance", never "compliant". AWS states that Part 11 applicability and IQ/OQ/PQ validation are the customer's job ([AWS GxP whitepaper](https://docs.aws.amazon.com/zh_cn/whitepapers/latest/gxp-systems-on-aws/appendix-21-cfr-11-controls-shared-responsibility-for-use-with-aws-services.html)). Ship a validation package (requirements, risk assessment, test evidence, trace matrix) and a matrix of who owns each control: AWS, us, or the customer.

**Check: Nitro Enclaves.** AWS Nitro Enclaves are sealed-off environments with no storage, no interactive access and no outside network, designed for CPU work such as handling keys. They are not a place to host GPU model inference. Per-customer VPC isolation is already the main control.

**Fix:** isolate inference with one AWS account and VPC per customer, private endpoints and customer-managed KMS keys. Use Nitro Enclaves only for key work, such as holding the ledger's signing key. Enclaves have no persistent storage, interactive access or external networking ([AWS](https://docs.aws.amazon.com/enclaves/latest/user/nitro-enclave.html)).

**The GPU layer.** vLLM is an open-source inference server that makes one GPU serve many requests at once (paged attention memory, continuous batching) behind an OpenAI-compatible API; SGLang and TensorRT-LLM are alternatives. GPUs are needed only in sovereign mode; APIs are cheaper everywhere else (section 15). Size them to the model: Gemma 4 31B fits one 48 GB L40S at FP8, or one 24 GB L4 at 4-bit with a 32K context; gpt-oss-120b fits one 80 GB H100; frontier-size open models such as DeepSeek V4 need multiple GPUs. Newer H200 and Blackwell GPUs carry more memory per card.

**Scale: asynchronous queues.** Parsing is batch work, so it runs through a job queue with worker pools (the overview: Celery + Redis Streams; alternatives: AWS SQS with ECS or Batch, Temporal, Ray for GPU batches). Three rules:

- **Idempotent jobs**: key every document by the hash of its file, so reprocessing yields the same fact IDs instead of duplicates.
- **Batch pages for the GPU** (the overview's "dynamic VLM batching") to keep utilization high.
- **Back-pressure**: queue depth, not user clicks, drives load on the GPUs and enterprise systems.

For scale intuition, with illustrative numbers: 50,000 pages at about 5 seconds each across 20 parallel workers is about 3.5 hours.

**Check: tenancy wording.** "Strict memory enclave isolation across client tenants" contradicts "single-tenant". If each customer has its own VPC, no tenants share memory. If you ever go multi-tenant SaaS, you need a tenant ID on every record, per-tenant encryption keys, separate vector namespaces, and no shared caches, including model prompt caches.

**Fix:** v1 is single-tenant, one AWS account and VPC per customer, so drop the "memory enclave" wording. If the product later goes multi-tenant, put a tenant ID on every row and enforce it with PostgreSQL row-level security ([AWS guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/rls.html)), with `FORCE ROW LEVEL SECURITY` so table owners cannot bypass it. Add per-tenant keys, separate vector indexes and no shared prompt caches.

## 20. One request end to end: the impurity walkthrough

The overview's example run is a good skeleton, and its sample output sentence contains four pharmaceutical science errors. That is itself the best argument for the project: even a careful expert document slipped, and a rules-aware checker would have caught every one.

**The run, step by step** (the step numbers match the badges on the section 10 diagram):

| # | Step | What happens | Fix or note |
| --- | --- | --- | --- |
| 1 | Request | User picks product, section, batches 2024-01 to 2024-12 and a data-freeze date | Add: the system proposes a **data manifest** and a human approves it |
| 2 | Start | Gateway checks the login token and role, opens a run ID, writes the first ledger entry | Roles are company-defined; Part 11 does not define "permissions" |
| 3–4 | Fetch | Ingestion calls MCP tools: `get_documents` (Veeva), `get_stability_matrix` (LIMS), `get_formulation_logs` (ELN) | Executes the manifest exactly |
| 5 | Parse | Scans go through OCR + VLM; LIMS rows are staged and checked, then become facts | Positions come from the table grid; values need two blind reads (section 12) |
| 6 | Store | Facts and relationships are staged, checked, then written to the fact store and graph | Reconcile each copy with its source; only independent routes count as agreement (section 6) |
| 7–8 | Compute | Validated functions compute trend, OOT and shelf life | Loads values by fact ID; the model types none (section 16) |
| 9 | Rules | Regulatory agent retrieves ICH text and compares results with limits | Comparisons in code; limits from the approved specification, thresholds from a rule table by modality, dose and guideline version, never from retrieval (below) |
| 10 | Draft | Model writes the narrative with fact placeholders | Provenance attached by the system, not the model |
| 11 | Check | Number and claim validator, cross-section consistency check | Missing in the overview as a named step |
| 12 | Review and sign | Reviewer clicks each number, sees the source box, signs; document hash goes to the ledger | Risk-based review depth (section 17) |
| 13 | Export | Signed section is pushed to Veeva Vault RIM | Veeva's own publishing and approval then take over |

**Check: the overview's sample sentence.** It reads: *"The total degradation products at Month 36 under accelerated conditions (40C/75% RH) reached 0.11%, remaining well within the ICH Q3B qualified threshold of 0.20%."*

1. **Accelerated studies do not reach Month 36.** Under ICH Q1A(R2), accelerated storage (40°C/75% RH) runs 6 months, for example at months 0, 3 and 6. Month 36 belongs to long-term storage (25°C/60% RH).
2. **Total vs individual.** ICH Q3B thresholds apply to **each individual** degradation product. Total degradation products are controlled by the product's own specification limit. Comparing a total with an individual threshold mixes two different things.
3. **The threshold depends on dose.** Q3B's qualification threshold is 1.0% below 10 mg/day, 0.5% for 10–100 mg, 0.2% for 100 mg–2 g, and 0.15% above 2 g (each "or a fixed daily intake, whichever is lower"). The 0.20% figure is only right for a 100 mg to 2 g daily dose, so the system must know the dose. The correct term is "qualification threshold".
4. **Q3B does not apply to biologics.** Q3B explicitly excludes biological and biotechnological products, yet the overview frames this as a BLA, and its stability grid (Month 1, frozen storage) looks like a biologic's. For a biologic the rules come from ICH Q6B and Q5C.

**Two data-sanity catches the checker should also make:**

- **Impossible dates.** Batch 2024-12 was made in December 2024, so Month-36 data cannot exist before December 2027. A simple rule (manufacture date + time point ≤ test date ≤ today) catches this.
- **Wrong source type.** Month-36 stability results normally come from LIMS or a stability report, not a release Certificate of Analysis.

**Fix:** the writer renders this sentence from typed facts, and code checks each part: storage condition against time point (accelerated runs 6 months under Q1A(R2)), individual against total, the Q3B threshold computed from the maximum daily dose, and the drug type choosing Q3B or Q6B and Q5C. Keep these rules in a versioned table, because the revised ICH Q1 is due for Step 4 in November 2026 ([ICH work plan](https://database.ich.org/sites/default/files/ICH52_Q1_EWG_WorkPlan_2026_0318.pdf)).

**Check: "historical limits from previous filings for the same molecule class"** (step 9) is precedent at best. A specification limit must be justified by this product's own data, safety qualification and the applicable guideline, not by what another product was allowed.

**Fix:** justify each acceptance criterion from this product's own data, as [ICH Q6A](https://database.ich.org/sites/default/files/Q6A%20Guideline.pdf) asks: batches used in toxicology and clinical studies, stability results, scale-up and validation batches, and expected analytical and manufacturing variability. Other products' limits may appear only as labelled context.

**Check: section choice.** The request names 3.2.P.5.5 (Characterisation of Impurities: what each impurity is and where it comes from), but the sample output is a stability trend statement, which belongs in 3.2.P.8.3 (Stability Data) and supports 3.2.P.5.6 (Justification of Specifications).

**Fix:** route content by rule. Trend statements go to 3.2.P.8.3, the identity and origin of impurities to 3.2.P.5.5, and the reasons for acceptance criteria to 3.2.P.5.6. Keep the mapping in a versioned table, since ICH M4Q(R2) is revising Module 3, with Step 4 planned for June 2027 ([ICH work plan](https://database.ich.org/sites/default/files/ICH53_M4QR2_EWG_WorkPlan_2026_0818.pdf)).

## 21. Module by module

Each module gets its own ingestion engine, built like the Module 3 engine, and they all feed one evidence graph through the write gate (sections 8 and 13). Module 2 and the label are written **from** that graph, never from scratch.

| Module | What it holds | Main sources | Data standards | What the platform does | Hardest check |
| --- | --- | --- | --- | --- | --- |
| 1 (regional) | Forms (US: 356h for NDA/BLA, 1571 for IND), cover letter, labeling, regulator correspondence, regional documents | RIM system, labeling system, past correspondence | Regional Module 1 specs; FDA Structured Product Labeling (SPL) XML | Fills forms from RIM data, drafts cover letters, drafts the label with every claim linked to evidence | Each label claim backed by Module 5 evidence; regional versions consistent |
| 2 (summaries) | 2.3 quality summary, 2.4 nonclinical overview, 2.5 clinical overview, 2.6 nonclinical summaries, 2.7 clinical summary | The evidence graph built from Modules 3–5 | ICH M4 structure | Generates tabulated summaries directly from data and drafts overviews with fact placeholders | Every number equals its Module 3/4/5 source; the summaries agree with each other |
| 3 (quality) | CMC | LIMS, Empower, ELN, ERP, CMO certificates | ICH Q guidelines; M4Q(R2) coming | The Module 3 engine (sections 10–20) | Sections 3 and 20 |
| 4 (nonclinical) | GLP study reports: pharmacology, pharmacokinetics, toxicology | CRO study reports (PDF), SEND datasets | CDISC SEND, Define-XML | Extracts findings, NOAELs (highest dose with no adverse effect) and exposures; checks report tables against SEND data | Safety margins (animal exposure at NOAEL ÷ human exposure) computed by code and consistent across 2.4, 2.6 and the label |
| 5 (clinical) | Protocols, statistical analysis plans, clinical study reports (CSRs), datasets, integrated safety and efficacy summaries | EDC system, statistical computing environment (SAS/R), safety database, CTMS | CDISC SDTM, ADaM, Define-XML; ICH E3 for CSRs; ICH M11 for protocols | Drafts CSR sections from protocol, analysis plan and output tables; drafts patient safety narratives; independently re-derives key results | Numbers in text = output table = analysis dataset; patient privacy |

**Plus one cross-cutting step at the very start: the content plan.** From the submission type (IND, NDA, BLA, supplement) and region, the platform proposes which documents each module needs, who owns each, and which data feeds it. A regulatory lead approves it, the same way the Module 3 data manifest is approved (section 11).

## 22. Modules 4 and 5: study data and reports

Clinical and animal data already arrive in strict, machine-readable formats, which makes Modules 4 and 5 better suited to the facts-first design than CMC. The platform must speak these formats natively.

**The CDISC standards, in plain words.** FDA's binding [Guidance on Standardized Study Data](https://www.cdisc.org/FDA-Final-Binding-Guidance-on-Standards) requires them for NDAs, ANDAs and certain BLAs, for studies starting from roughly late 2016 onward:

| Standard | What it is | Example |
| --- | --- | --- |
| SEND | Animal study data in standard tables | Body weights, lab values, microscopic findings per animal |
| SDTM | Clinical trial data as collected, in standard "domains" | DM (demographics), AE (adverse events), LB (labs), VS (vital signs) |
| ADaM | Analysis-ready datasets built from SDTM | ADSL (one row per subject), ADAE, ADTTE (time to event) |
| Define-XML | The data dictionary describing every dataset and variable | Origin and derivation of each variable |
| Controlled terminology | Fixed vocabularies for values | Standard units, test names |

These are submitted in Module 5 (clinical) and Module 4 (nonclinical) with reviewer's guides, and analysis programs for key efficacy tables are submitted too.

**The traceability chain the platform walks:** case report form → SDTM → ADaM → output table (TLF: tables, listings, figures) → CSR text → Module 2 → label. Every number in the last three must trace back through the first four.

**What the platform adds at each link:**

1. **Reads numbers from validated outputs**, never computes official results. Efficacy and safety statistics belong to the sponsor's validated SAS or R programs.
2. **Independent re-derivation of key results.** Pharma already checks important outputs by “double programming”: a second programmer reproduces each table from the specification without looking at the first programmer's code; if the second copied the first, both would share any mistake and still agree. The platform automates part of this for headline numbers (patients randomized, completers, deaths, demographics, and efficacy results where the analysis plan is precise) from the SDTM data (the collected data in standard tables) with its own validated library, and compares them subject by subject. It does not use ADaM, whose derived flags (yes/no markers such as “completed Week 24”) are the sponsor's own work. It flags any mismatch. A test of this on the real CDISC pilot trial reproduced the study report's headline facts exactly (section 30). It is a check, not a replacement.
3. **CSR drafting by ICH E3 structure.** Methods sections come from the protocol and analysis plan; results sections from the output tables, with fact placeholders.
4. **Patient safety narratives.** Short case histories for deaths, serious and notable adverse events, drafted from the SDTM adverse event, medication and lab records. High volume, highly repetitive, and every fact in them is checkable against the data, so a very good fit.
5. **Module 4 extraction.** NOAELs, exposure values (AUC, Cmax) and target-organ findings come from GLP reports and are checked against SEND. Safety margins are computed by code.

**Evidence that this is feasible:** Weave Bio and Takeda reported cutting nonclinical summary drafting from about 100 hours to 3, with 95% source fidelity ([HIT Consultant, Sept 2026](https://hitconsultant.net/2026/09/01/weave-bio-takeda-collaboration-ai-regulatory-automation-ind-drug-development/)). These are company-reported figures. The 95% also shows the gap this platform targets: the remaining 5% is what deterministic checks should catch.

## 23. Module 2 summaries and labeling

Module 2 and the label are **views** over the evidence graph. That single design choice is what keeps them consistent with Modules 3 to 5 automatically.

**Module 2, part by part:**

| Part | Built from | How |
| --- | --- | --- |
| 2.3 Quality Overall Summary | Module 3 facts | The Module 3 engine. Under the draft ICH M4Q(R2), 2.3 becomes the primary assessed quality document (section 29), so this matters more, not less |
| 2.4 Nonclinical Overview | Module 4 facts and claims | Drafted with placeholders; safety margins from code |
| 2.6 Nonclinical Written and Tabulated Summaries | Module 4 facts, SEND | The **tabulated** parts are generated straight from data as tables, with no model in the loop |
| 2.5 Clinical Overview | Module 5 facts and claims | Drafted; benefit-risk conclusions written and signed by named clinical experts |
| 2.7 Clinical Summary (biopharmaceutics, clinical pharmacology, efficacy, safety) | ADaM-based outputs, CSRs | Tables generated from data; text drafted with placeholders |

**Labeling.** The US prescribing information follows a fixed format: Highlights, then 17 numbered sections (1 indications, 2 dosage, 5 warnings, 6 adverse reactions, 12 clinical pharmacology, 14 clinical studies, and so on). FDA also receives it as SPL XML. The platform:

1. Keeps a **label claim traceability matrix**: each label statement linked to its supporting evidence in Modules 2–5. Industry teams maintain this by hand today.
2. Drafts label text from the evidence graph with placeholders, so the adverse reaction table in section 6 can never drift from the safety outputs.
3. Derives regional versions (EU summary of product characteristics, Japan package insert) from the same claim set, with regional wording rules.

**Guardrail:** label wording is negotiated with the regulator line by line. The platform drafts, links and checks; the labeling team decides. Every negotiated change is captured as a new version of the claim, so the history is never lost.

## 24. Module 1, multi-region reuse, publishing and lifecycle

Build one global evidence graph with regional overlays, and integrate with existing publishing tools rather than rebuilding them. Publishing is a mature commodity; the platform's value is making sure what gets published is right.

**Module 1 is the regional wrapper.** US: forms 356h or 1571, cover letter, user fee, patent and financial disclosure information, labeling. EU: application form, product information (SmPC, package leaflet), risk management plan. Japan: Japanese-language administrative documents. The platform fills forms from RIM master data and drafts letters from the content plan.

**Multi-region reuse.** Modules 2 to 5 are harmonized by ICH, so one evidence graph serves every region. The regional deltas are narrow and listable: Module 1, pharmacopoeia references (USP, Ph. Eur., JP), regional labeling formats, language, and some regional Module 3 content (3.2.R). The platform holds a **core dossier plus regional overlays**, and the consistency engine checks that overlays never contradict the core.

**Publishing: integrate, then check.** Assembling the eCTD (folder tree, XML backbone, lifecycle operations such as new, replace and delete, hyperlinks, bookmarks) is done well by existing tools: Veeva's submissions publishing, Lorenz docuBridge, Extedo. The platform hands finished documents to them and adds **pre-publishing checks**: PDF rules (embedded fonts, bookmarks, working links), correct document granularity and lifecycle operation, and the regional validation rules a gateway applies automatically before any human reviewer sees the submission.

**eCTD v4.0 is arriving region by region** ([IntuitionLabs summary](https://intuitionlabs.ai/articles/ectd-v4-implementation-guide-timelines); several dates come from consultancies, so confirm with each agency):

| Region | Status |
| --- | --- |
| US (FDA) | Accepted voluntarily for new applications since 16 Sept 2024; no mandatory date announced |
| EU (EMA) | Optional for new centralized applications from 22 Dec 2025; mandatory reported for 2027 |
| Japan (PMDA) | Reported mandatory from 1 April 2026 |
| Health Canada | Reported voluntary 2026, mandatory 2028 |

v4.0 gives every document a unique ID that later submissions can **reuse by reference**, tags documents by "context of use" instead of folder position, and uses controlled vocabularies. That suits a graph-based platform: give each evidence-graph document the same identity as its v4.0 document ID, and reuse and lifecycle tracking come almost for free.

## 25. After submission: questions, commitments and changes

A submission is not the end. Regulator questions, promises made in answers, and years of post-approval changes all draw on the same evidence, so the graph keeps paying off long after the first filing.

**Answering regulator questions.** FDA sends information requests during review; EMA sends formal lists of questions. The flow:

1. **Intake and classify** each question by topic and the dossier sections it touches.
2. **Retrieve evidence** from the graph, not just text search, so the draft answer cites the exact facts and studies.
3. **Draft** with fact placeholders, route to the right experts, and track deadlines.
4. **Check consistency**: the answer must not contradict what the dossier already says. If it changes a fact, the change propagates (section 8) and the affected sections are queued for an amendment.

Weave Bio already offers question intake and response drafting, and Takeda uses it ([HIT Consultant](https://hitconsultant.net/2026/09/01/weave-bio-takeda-collaboration-ai-regulatory-automation-ind-drug-development/)). The difference here is step 4.

**Commitments.** Answers and approvals create obligations: post-marketing requirements and commitments, promised stability updates, study reports due by a date. Each becomes a tracked item in the graph, linked to the evidence that will fulfil it, with reminders.

**Post-approval changes.** This was the strongest future idea in section 32, now platform-wide. A proposed change (a new supplier, site, test method or label update) runs through the graph to list every affected product, region and section, and the filing category each region requires: in the US a prior approval supplement, a changes-being-effected supplement or an annual report; in the EU a Type IA, IB or II variation. The platform then drafts the variation package from the updated evidence.

**Later scope:** periodic safety reports and annual reports reuse the same graph, but they belong to a later phase.

## 26. Privacy, security and validation with patient data in scope

Module 5 brings patient-level data into the platform, which changes three things: privacy law now applies, a new access rule (blinding) appears, and the redaction agent from the original overview becomes genuinely necessary.

**Privacy.** Clinical datasets use subject codes instead of names, but under GDPR pseudonymized data is still personal data. Patient narratives, listings and case report forms are the most sensitive. Rules:

- **Minimize what models see.** Most drafting works from aggregated output tables. Patient-level records go to a model only for narratives, and only to a model running inside the sponsor's environment.
- **Purpose-limited access**: per program, per study, per role, all logged.

**Blinding firewalls.** While a trial is still running, treatment assignments are hidden from most of the sponsor's team so they cannot bias it. A platform that reads trial data must enforce this: unblinded data visible only to authorized roles, and nothing derived from it leaking into documents other people read. A single leak can compromise a trial.

**Redaction becomes a real feature.** In section 14, a HIPAA redaction agent made little sense for CMC data. For clinical documents it is needed: CSRs and other clinical documents are published under transparency rules such as EMA Policy 0070, Health Canada's public release of clinical information, and the EU Clinical Trials Regulation. These require anonymizing patients and removing commercially confidential information. The platform can propose redactions with reasons, for a human to approve.

**Validation.** Everything in sections 18 and 28 still applies: Part 11, the ledger, frozen GEPA prompts, controlled Agent Skills. Two additions:

- **ICH E6(R3)**, the revised Good Clinical Practice guideline adopted by ICH in January 2025, expects computerized systems used for trial data to be fit for purpose and validated in proportion to risk. Anything that touches clinical data must meet it.
- **A credibility file per use.** For each AI use (narrative drafting, CSR drafting, question answering), keep a short record following FDA's draft framework: question, context of use, model risk, tests run, results. Most uses stay in "drafting a submission", but the record proves it.

## 27. "Why modern AI makes this possible", checked

The "why now" argument is broadly correct: in 2021 this system could not have been built to this standard. A few of the before/after pairs are overstated, and the two strongest drivers are missing.

| Capability | Overview: 2021 → 2026 | Verdict |
| --- | --- | --- |
| Context window | 2k–8k tokens → 1M+ | True. Opus 4.6, Opus/Sonnet 5.5 and DeepSeek V4 all offer 1M. Caveat: long context is not perfect recall (Opus 4.6 scored 76% on a long-context retrieval test, so it still misses), so exact values still come from the fact store |
| PDF parsing | OCR + regex → vision-language models | Overstated gap. Layout-aware OCR already existed by 2021 (AWS Textract, Azure Form Recognizer, LayoutLM). The real change is **semantic** understanding of messy layouts |
| Integration | Point-to-point APIs → MCP | True. MCP only appeared in November 2024. The adapters still have to be written |
| Retrieval | Naive vector search → hybrid Graph RAG | Partly. Hybrid keyword + vector search and knowledge graphs predate 2021. What is new is LLMs making graphs easy to build and query (for example text-to-Cypher) |
| Arithmetic | Probabilistic → code sandboxes | True in spirit. Code always computed exactly; what changed is models reliably writing code and calling tools |
| Workflow | "Linear chains (LangChain 2021)" → LangGraph | Direction true, date wrong: LangChain launched in October 2022 and LangGraph in January 2024 |

**Two drivers the overview misses, and they are the strongest:**

1. **Reliable structured output and tool calling.** Since 2024 models can be constrained to emit valid JSON matching a schema and to call typed tools. This is what makes "model outputs a fact with a pointer" and "model calls `shelf_life(fact_ids)`" dependable, far more than raw context size.
2. **Regulators started writing AI rules.** FDA's draft AI credibility guidance (January 2025), the FDA–EMA Good AI Practice principles (January 2026) and the EU's draft GMP Annex 22 (July 2025) give sponsors a framework for defending AI-assisted work. Before them, no QA head would sign off. Regulatory clarity is a precondition for buyers, not a footnote.

## 28. Latest GenAI and agentic technologies to add

Ten technologies from 2025–2026 earn a place, and each one strengthens a box that already exists (see the section 10 diagram) rather than adding a new layer. **GEPA is the strongest addition**: it improves every prompt in the system automatically, using the checkers this project already has. **JEPA is real and important research, but it does not fit the core of this project**; it has two narrow, optional uses, described below.

### GEPA: self-improving prompts

**What it is.** [GEPA](https://arxiv.org/pdf/2507.19457) (Genetic-Pareto) is a prompt optimizer from UC Berkeley, Stanford, Databricks, MIT and others, accepted as an ICLR 2026 oral paper. It runs your pipeline on example inputs, has a strong model **read the traces and the error messages in plain language**, and writes improved prompts. It keeps a Pareto frontier of candidate prompts (each best on different examples) instead of polishing a single one, and can merge lessons from different candidates. In the paper it beat GRPO, a reinforcement-learning method that changes model weights, by about 6% on average (up to 20%) while using up to 35× fewer runs, and beat the older MIPROv2 optimizer by over 10%. It ships as `dspy.GEPA` in the [DSPy library](https://dspy.ai/current/api/optimizers/GEPA/overview/).

**Why it fits this project so well.** GEPA learns best from rich written feedback, and this project already produces exactly that from its deterministic checkers. When the CoA extractor gets a row wrong, the cross-check can say: *"Impurity B, Month 12: extracted 0.14, expected 0.014; decimal shifted; the footnote says results are in %."* When the writer overclaims, the validator can say: *"Sentence 3 says all batches met specification, but batch 2024-07 failed dissolution."* GEPA reads hundreds of such messages and rewrites the instructions to stop those mistakes.

**Where it runs: offline only.** GEPA tunes prompts during development. The winning prompt is then frozen, regression-tested on the golden set, version-pinned and logged in the ledger like any other change (section 30, model change control). Production never edits its own prompts, which keeps validation intact.

```python
import dspy

class ExtractCoA(dspy.Signature):
    """Extract every result row from a Certificate of Analysis page."""
    page_text: str = dspy.InputField()
    rows: list[dict] = dspy.OutputField(desc="analyte, value, unit, limit")

def metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
    errors = compare_rows(gold.rows, pred.rows)      # deterministic checker
    score = 1 - len(errors) / len(gold.rows)
    return dspy.Prediction(score=score, feedback="\n".join(errors) or "All rows correct.")

optimizer = dspy.GEPA(metric=metric, auto="light",
                      reflection_lm=dspy.LM("anthropic/claude-opus-5-5"))
better = optimizer.compile(dspy.Predict(ExtractCoA), trainset=train, valset=val)
```

**Watch out:** it can overfit its training examples, and it can learn to satisfy the checkers it is tuned against rather than to be right. Judge the result on a held-out set it never saw, graded by checks it was never tuned on plus a human-labeled golden set (section 30). The real Lek batch values rendered as scanned tables (sections 12 and 36) give you hundreds of labeled examples.

### JEPA: world models, an honest fit check

**What it is.** JEPA (Joint Embedding Predictive Architecture) is Yann LeCun's alternative to generative models. A normal model learns by predicting the missing raw data: the next word, the missing pixels. JEPA predicts the missing part's **meaning** (its embedding) instead, which pushes it to learn structure and ignore noise. The family so far:

- **I-JEPA** (images, 2023).
- **[V-JEPA 2](https://github.com/facebookresearch/vjepa2)** (video, June 2025; 300M–1B parameters, MIT license). Its action-conditioned version, V-JEPA 2-AC, plans robot arm movements; V-JEPA 2.1 followed in March 2026.
- **[LLM-JEPA](https://arxiv.org/html/2509.14252v2)** (September 2025, Huang, LeCun, Balestriero): adds a JEPA loss to language-model training using **two views of the same knowledge**, such as a text description and its code. It improved natural-language-to-regex, text-to-SQL and GSM8K math at 1B–8B model sizes, and resisted overfitting better than plain fine-tuning.
- **AMI Labs**, LeCun's new company, [raised a $1.03 billion seed round in March 2026](https://torontostarts.com/2026/09/16/ami-labs-world-models-jepa/). Its targets are robotics, driving, wearables and industrial processes, and it had no product yet as of September 2026.

**Why it is not in the core.** This project's core job is reading documents exactly and checking numbers. JEPA models do not generate text and do not read documents better than today's OCR plus vision models, and no production JEPA model for documents exists. Putting one in the main path would add risk without adding accuracy.

**Two places it could genuinely help (optional research track, after the MVP):**

1. **LLM-JEPA for a small local extractor.** This project naturally has two views of the same knowledge: the text of a scanned table row and its verified fact JSON, or a narrative sentence and the facts it states. Fine-tuning a \~1B local model with the LLM-JEPA loss on those pairs might make extraction more robust than plain fine-tuning. It is testable with pairs built from the real Lek batch values rendered as scanned tables (section 36).
2. **Self-supervised anomaly flags on raw signals.** A JEPA-style encoder trained on chromatogram traces or stability curves could flag unusual ones for human review, as an early out-of-trend warning. It would **never** be the source of a reported value, which keeps it consistent with the rule in section 6. This also points toward the process-analytics future scope (section 32), the same industrial area AMI Labs targets.

**Verdict:** a strong thesis chapter or paper, not an MVP component.

### The other nine technologies, and where each plugs in

| Technology (when) | What it is | Plugs into (section 10 box) | What it adds | Watch out |
| --- | --- | --- | --- | --- |
| [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) (Claude, Nov 2025; now standard) | The schema is compiled into a grammar, so output always matches it | Scans: OCR + VLM; Writer model | Every fact proposal is valid JSON with the right fields; no parse failures or retries | Schemas cannot express numeric min/max, so ranges are still checked in code; cannot be combined with Citations in one call |
| [Citations](https://platform.claude.com/docs/en/build-with-claude/citations) (Claude) | Answers point to exact passages and page numbers in supplied documents | Rules check | Every regulatory statement quotes the exact ICH passage and page it relies on | Works only on PDFs with a text layer (fine for ICH PDFs); run as a separate call from structured outputs |
| [Local document VLMs](https://www.spheron.network/blog/best-open-source-ocr-vlm-self-host-gpu-cloud-2026/): PaddleOCR-VL-1.6, Granite-Docling, DeepSeek-OCR, dots.ocr | Small open models that convert page images to structured text and tables | Scans: OCR + VLM | Run inside the VPC on one GPU. PaddleOCR-VL-1.6: 0.9B parameters, Apache-2.0, 96.33% on OmniDocBench v1.6; Granite-Docling: 258M, outputs Docling JSON | Keep the two-route cross-check; confirm each model's bounding-box output before relying on it |
| [ColPali / ColQwen](https://huggingface.co/blog/manu/colpali) visual retrieval | Searches page **images** directly with a vision model and late-interaction matching, no OCR needed | Knowledge layer | Finds the right scanned page ("which CoAs mention Impurity B?") even when OCR misread the text | Larger multi-vector index; use it to find pages, never to read values |
| MCP [Tasks and elicitation](https://workos.com/blog/mcp-2025-11-25-spec-update) (Nov 2025) and the [2026-07-28 spec](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) | Long jobs return a task handle; a server can pause and ask the human for input; W3C trace context in calls | MCP servers | Long LIMS and Empower pulls run asynchronously; the server can ask the reviewer to approve the data manifest mid-call; every call carries a trace ID into the audit trail | The 2026-07-28 release is breaking (stateless core, Tasks moved to an extension): pin one spec version |
| [Advanced tool use](https://anthropic.com/engineering/advanced-tool-use) (Claude, Nov 2025): Tool Search, Programmatic Tool Calling, Tool Use Examples | Load tools on demand; the model writes a short script that calls tools in a sandbox; example calls attached to tool definitions | Orchestrator; Statistics | The model composes calls such as `shelf_life(fact_ids)` in a script, so raw values never pass through its context (37% fewer tokens reported). Tool examples teach exact fact-ID formats (72% → 90% parameter accuracy reported) | Log every generated call script in the ledger |
| [Agent Skills](https://siliconangle.com/2025/12/18/anthropic-makes-agent-skills-open-standard/) (Oct 2025; open standard Dec 2025) | Versioned folders of instructions, templates and scripts that an agent loads when relevant | Writer model; Rules check | One skill per section type, e.g. a 3.2.P.8.3 stability skill with its template, required tables, phrasing rules and examples. Regulatory experts can review it like an SOP | Treat each skill change as a controlled document change |
| [OpenTelemetry GenAI conventions](https://john-hodge.com/blog/opentelemetry-genai-semantic-conventions/) | Standard trace format for model calls, agent steps, tool calls, retrieval and evaluations | Audit ledger | Every step becomes a standard trace that can go to an observability tool (such as Langfuse) and be hashed into the ledger | Still "Development" status as of July 2026: pin the version |
| [A2A protocol](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) (v1.0, Linux Foundation) | Standard for agents of different companies to talk to each other; complements MCP | Next to Veeva Vault | Later: hand a signed section to Veeva's or a CRO's agents through a standard. 150+ organizations; built into Azure AI Foundry and Amazon Bedrock AgentCore | Not needed for the MVP |

### Considered and left out

- **Reinforcement-learning fine-tuning (GRPO and similar):** changes model weights, so every run means re-validation. GEPA got bigger gains with prompts alone in its own paper.
- **Self-organizing agent swarms:** unpredictable paths cannot be validated (section 14).
- **Long-term agent memory across filings:** risks carrying one product's facts into another product's dossier. Each run starts only from its approved data manifest.
- **Computer-use agents for CMO portals:** maybe later, only as a supervised, read-only download helper. Never typing values.
- **JEPA in the core path:** see above.

### What to add to the student build (section 36)

1. **GEPA** on the CoA extractor and the writer, scored by your own checkers. The biggest win for the least work.
2. **PaddleOCR-VL or Granite-Docling** locally instead of a cloud OCR service.
3. **Structured outputs** for fact extraction and **Citations** for ICH quotes.
4. **OpenTelemetry traces into Langfuse**, hashed into the ledger.
5. **One Agent Skill** for 3.2.P.8.3 stability writing.
6. Optional research chapter: **LLM-JEPA** fine-tuning of a \~1B model on text ↔ fact-JSON pairs built from the real batch data rendered as scans, compared with plain fine-tuning on extraction accuracy.

**Updated one-breath pitch:** "…every number comes from a verified fact store, and the prompts that read the documents are optimized with GEPA against the system's own deterministic checkers."

## 29. The structured-data future

Regulators are moving from documents toward structured data, one standard at a time. The strategic bet: **store evidence as structured data and render documents as views of it.** Document-first tools will have to be rebuilt as these standards land; an evidence-graph platform simply adds another output.

| Standard | What it does | Status | What the platform does with it |
| --- | --- | --- | --- |
| ICH M11 (CeSHarP) | A structured, machine-readable clinical protocol: guideline, template and technical specification with defined data elements | Adopted by ICH 19 Nov 2025; FDA final guidance 22 May 2026; in effect in the EU from 11 June 2026; not mandatory ([Sakara Digital](https://sakaradigital.com/blog/ich-m11-machine-readable-protocol-clinical-systems/)) | Reads M11 protocols as data, so CSR methods sections, 2.7 descriptions and trial-registry entries fill themselves |
| CDISC USDM | The data model for study definitions, built with TransCelerate's Digital Data Flow and aligned with M11 | In use; CDISC standard | The exchange format for protocol data into the graph |
| ICH M4Q(R2) | Restructured quality modules: 2.3 becomes the primary assessed document; Module 3 the supporting repository; most parts follow Description, Manufacture, Control, Storage | Step 2 draft May 2025; consultation closed Oct 2025; Step 4 targeted June 2027 ([EUREG](https://eureg.ie/ich-m4qr2-modules-2-3-and-3-2/)) | The Module 3 fact store maps onto it; it is designed to prepare for a forthcoming ICH guideline on structured quality submissions |
| FDA PQ/CMC | FDA's program to standardize quality data elements | Ongoing | Same target as M4Q(R2): CMC facts submitted as data |
| ISO IDMP | Standard identifiers for medicinal products and substances | Implemented through EMA's master-data services | Product master data in the graph, shared with Module 1 and labeling |
| eCTD v4.0 | Message-based submission with reusable document IDs | Rolling out (section 24) | Graph document IDs = v4.0 IDs |

**Practical rule for the build:** every evidence item gets a stable ID and machine-readable fields from day one, even while outputs are still Word and PDF. That costs little now and turns each new standard into an export, not a rewrite.

## 30. Technical challenges

The overview's five challenges are real, but it misses the hardest one: **how do you validate a system whose AI parts can answer differently each run?** The answer shapes the whole architecture: validate the deterministic controls around the model, not the model itself.

**The overview's five, judged:**

| Challenge | Overview's mitigation | Verdict |
| --- | --- | --- |
| 1. Zero hallucination tolerance | Models write Python for math; a hard block stops unverified numbers | Right idea. Strengthen with fact placeholders and a claim validator (section 6). Hallucination is not only numbers: a wrong batch ID, method name, or "no new impurities were observed" are claims too |
| 2. Part 11 compliance | Immutable Postgres ledger with SHA-256 chains | Necessary, not sufficient; close the three holes in section 18. The real Part 11 challenge is validation (below) |
| 3. Data sovereignty | Commercial region per customer, Nitro Enclaves, local vLLM | Right goal. Fit the choices to one region per customer: pgvector instead of Pinecone, a model the region lists, and a region check for Aura and OpenAI embeddings. Add contractual zero-data-retention with any model provider |
| 4. Ingestion latency | Celery + Redis Streams, GPU batching | Fine; add idempotency keys (section 19) |
| 5. Token cost | Local model for preliminary work, Claude for synthesis | Fine; add prompt caching, and extract facts once so no step re-sends a million tokens |

**What the overview misses:**

1. **Validating non-deterministic AI.** FDA's January 2025 draft guidance defines a 7-step credibility framework: define the question, define the context of use, assess model risk, plan, execute, document, decide adequacy. Model risk = **model influence** (does a human check the output?) × **decision consequence** (what happens if it is wrong?). Notably, the draft [excludes AI used "to streamline operations (e.g., drafting a regulatory submission)"](https://www.dlapiper.com/en/insights/publications/2025/01/fda-releases-draft-guidance-on-use-of-ai) when it does not affect patient safety or data reliability. This project's design fits that well: the AI drafts and extracts, while every number is produced by validated code and verified by a human, so the AI's influence on the evidence is low. Validation then targets the controls: extraction cross-checks, the statistics library, the validator, and the review workflow.
2. **Ground truth for testing.** Approved Module 3 sections are confidential, and FDA's public review packages contain reviewers' summaries with most numbers redacted. Public data still covers most testing (section 36): real batch values rendered as scans, real FDA reviews and labels, and a real clinical trial's datasets with its study report. What only a design-partner company can supply is a full dossier with its raw data and real scans, for final validation. The planted test errors must also come partly from outside the team (below).
3. **Shared vocabulary.** The same impurity, test or unit is named differently across sites and CMOs. The system needs a controlled vocabulary with synonyms, maintained by people. FDA's own PQ/CMC initiative to standardize quality data elements points the same way.
4. **Model change control.** Pin exact model versions; any change of model, prompt or library version triggers regression tests on a golden set before release.
5. **Late data.** A new stability pull arrives after drafting. With fact lineage, the system finds every sentence and table that depends on the changed data and re-runs only those.
6. **Prompt injection.** A document can contain text that tries to instruct the model. Treat all document text as data, restrict tools to read-only, and never let document content change the workflow.
7. **Human factors.** Writers must trust the tool without over-trusting it (section 17), and it must fit into Word and Veeva, where they already work.
8. **Liability.** The sponsor's QA stays responsible for what is submitted. Contracts and the product's claims must say so plainly: the tool assists and proves; it does not certify.
9. **Format transitions.** FDA has [accepted eCTD v4.0 voluntarily since 16 September 2024](https://intuitionlabs.ai/articles/fda-ectd-requirements-guide), with no mandatory date yet. Output documents must fit both v3.2.2 and v4.0 publishing.

### The same flaw elsewhere: checks that cannot fail

**The pattern.** The OCR + VLM flaw in section 12 was a check that could not catch a common error: the VLM was shown the OCR text and tended to repeat it, so the two readings agreed even when both were wrong. After fixing it, every other check in this design was audited for the same shape. A check is worthless when its result does not depend on whether the thing it checks is right, and that happens in three ways: it reads the same input as the thing it checks; it tests a value but not what the value means (which batch, which population, which version); or the people who built it also grade it. Ten more checks had one of these problems.

**The independence rule.** A check counts only if it can fail. It needs an input of its own, it must test meaning as well as value, and it must be graded by tests its builders did not write.

| # | Check (section) | Why it could pass when wrong | What would go wrong midway | Fix, now written into that section |
| --- | --- | --- | --- | --- |
| 1 | Number validator: “every digit traces to a fact” (6) | It asks whether the number exists in the fact store, not whether it is the right fact | A value from the wrong batch or test passes; results written in words are never checked | Every number is a placeholder bound to one fact, and the batch, test, time point and unit around it must match that fact; number words are rendered from facts |
| 2 | Two-route agreement (6) | The two routes are often one: a CoA printed from LIMS, or a dataset copied into a second package | A wrong LIMS value agrees with its own printout | Each fact records its lineage; copies never count as agreement; a copy is compared with its source |
| 3 | Consistency engine (8) | Placements rendered from one fact always agree, and two facts with one name can mean different things | Green checks while the exported file carries a hand edit or a stale table; false or hidden conflicts between definitions | Re-read the final exported files with an independent parser; each fact carries its definition (population, coding list such as the race categories used, method and document version) |
| 4 | Clinical re-derivation (22) | Recomputing from ADaM reuses the sponsor's own derived flags (yes/no markers such as “completed Week 24”) | A wrong completer or population flag is “confirmed” | Re-derive headline numbers from the SDTM data (the collected data in standard tables) by the analysis plan, never from the sponsor's code, and compare subject by subject |
| 5 | Claim checker (7) | The same model family drafts the text and decides which parts are claims | A claim the model does not notice is never checked | A model from a different family, plus fixed rules, extracts claims; every sentence ends up as a number, a claim or a non-claim; non-claim labels are shown to the reviewer, and a sentence with “all”, “every”, “no”, “none” or “only” can never be marked non-claim |
| 6 | Limit and threshold choice (13, 20) | The comparison is code, but the limit it compares against comes from retrieval | Correct arithmetic against a threshold for the wrong dose or guideline version | Limits from the approved specification; thresholds from a rule table keyed on modality, maximum daily dose and guideline version, entered twice by different people and tested against the guideline's own examples; retrieval supplies only the quote |
| 7 | Human review (17) | The reviewer sees the system's value and its green check before the source | Agreement by default: the rubber-stamping section 17 warns about | For high-risk values the reviewer enters the value from the source first; seeded challenge items per reviewer |
| 8 | GEPA prompt tuning (28) | Prompts are tuned against the same checkers that later grade them | The prompt learns to please the checkers rather than to be right | Release decided on checks GEPA was never tuned on, plus a human-labeled golden set |
| 9 | Seeded-error studies (30, 36) | The team that built the checker also invents the errors | The errors the builders can imagine are the ones they already catch | Part of the errors come from outside: real FDA complete response letters, real OCR misreads, a classmate who has not read the checker code |
| 10 | Data manifest approval (11) | A person approves the list the model proposed | A missing batch or study is invisible, since nobody sees what is not listed | Compare the manifest with an inventory from a second system and show what was left out |

**Test 1: the number validator, on the 1,005 real Lek batches.** In 400 simulated sections of ten batches each, ten facts per section were each changed five ways: 4,000 picks of 2,894 distinct real facts (changes that left the printed number the same were dropped). Each changed value was then checked the old way: does the same number exist among the facts?

| Error | Changed values | Still pass: number exists in the section | Still pass: number exists anywhere in the product |
| --- | --- | --- | --- |
| Wrong batch, right test | 3,128 | 100% | 100% |
| Wrong test, right batch | 3,595 | 100% | 100% |
| Last digit off by one | 4,000 | 50.4% | 86.4% |
| Decimal point moved one place (0.14 to 1.4 or 0.014) | 4,000 | 3.9% | 8.8% |
| Two digits swapped | 2,710 | 3.5% | 24.1% |

The first two rows are 100% by definition, and that is exactly the problem: a wrong binding is still a real fact, so a value-only check cannot see it. Half of all last-digit slips pass too, because real batch values cluster and one section holds many identical numbers. Bound placeholders remove typed-number errors by construction, because the model never types a number. Wrong bindings are different: the model still picks which fact goes in which sentence. They are caught only if the batch and test named in the sentence come from the same fact or are checked against it, and that check must itself be tested with planted errors.

**Fix for wrong binding: six approaches compared, then built and tested on the stability writer.** Wrong binding means the model picks a real fact but puts it where it does not belong, such as the lowest result called “highest”. No single approach removes it. Each one removes one kind.

| Approach | Stops wrong binding? | What still gets through | Cost |
| --- | --- | --- | --- |
| 1. One fact holds value, batch and month | Yes, by construction, for value with batch and value with month | Which fact goes where (lowest called highest) | None |
| 2. Every role, test, batch and time word must sit next to a matching placeholder, or not appear | Yes, for the words on the list | Words not on the list (“gradually”); a test name in mid-sentence that the registry lacks | More drafts rejected |
| 3. Code writes the content plan; the model only words it | Strongest: the model never chooses the claim | Wording between the slots | Stiffer text. Used in part (code fixes the required facts, trend and pass/fail); a full sentence-by-sentence plan is held in reserve |
| 4. Grammar-limited output (llama.cpp GBNF, JSON schema) | Shape only. It cannot tell which fact belongs in a slot, unless the grammar is a sentence plan, which is approach 3 | Anything the grammar allows | Needs llama.cpp's server (Ollama takes JSON schema only); format limits can lower quality |
| 5a. Re-read the finished text against the raw table with rules | Yes, for any value, batch or month that does not match the data | A wrong word around a correct value | Milliseconds, no model |
| 5b. Re-read with a trained entailment model | Partly: recall 0.947, precision 0.837 on the authors' expert set | About 1 miss in 20, plus false alarms | A model run per paragraph. A flag for the reviewer, not a gate |
| 6. Data-to-text research | Shows the risk is real. No guarantee | See below | None |

**What the research says.** Thomson and Reiter (2020) found 418 errors in 21 machine-written basketball summaries: 184 numbers, 105 names, 80 words, 19 context (arXiv 2011.03992). Kasner and Dušek (2024) found a semantic error in over 80% of outputs from open models (arXiv 2401.10186). Their template-first pipeline (2022, arXiv 2203.16279) is the closest published match to approach 3. The entailment check is Dušek and Kasner 2020 (arXiv 2011.10819). Tam et al. (2024, arXiv 2408.02442) report that forcing a format can lower reasoning quality; only the abstract was read.

**Recommended: 1 + 2 + 5a, with the content plan (3) as the first reserve.** The model writes only words around placeholders. Code supplies one fact per result, the required facts, the trend and pass/fail. A draft is rejected if a role, test, batch, time or comparison word does not match its placeholder, if a sentence starts with anything but a connecting word or the tested attribute, or if its words contradict the computed trend or pass/fail. The accepted paragraph is rendered and re-read against the raw table. Add the full plan (3) if the audit below accepts one wrong paragraph. Add grammar limits (4) only if too many drafts are rejected. Use 5b as a flag for the human reviewer. Everything is free and deterministic except 5b.

**Planted-error test, no model involved.** On 1,008 synthetic sections per run (8 fixed, 1,000 random), one error was planted at a time: 23 kinds in the draft (role word flipped, wrong fact under a role word, start and end swapped, another test's name, an unlisted test name, wrong condition word, trend flipped, “in all batches” overclaim, pass/fail flipped, out-of-specification result left out, batch or time named in words, cause claim, typed number, typed batch ID, unknown placeholder, one batch's result called “the initial range” or “initial results”, a change described between two batches' results, results from different months placed “at the last time point”, a time point repeated after a range, “ranging from” the first to the last range while other results lie outside, the condition called out of specification) and 4 hand edits to the finished text (digit, batch label, month on a result, month on a range). Three runs with different seeds planted 7,836, 7,803 and 7,865 errors, about 300 per kind, and caught all of them. All 1,008 correct paragraphs in each run passed, as did 10 correct paraphrases written by hand. Zero misses in 300 tries still allows a true miss rate of up to 1.0% (95% bound). Twenty-six wrong paragraphs, written by hand or taken from the audit below, are also all caught; the checks were fixed after seeing them, so that list shows the gaps stay closed. It is not a blind test.

**First audit of the model's own drafts: the checks missed errors.** Gemma 4 (e4b) wrote 160 drafts on the laptop; 102 were accepted. Each accepted paragraph was read against the data table (by Claude, not by the checks): 61 ok, 30 awkward, 7 misleading, 4 wrong. The 4 wrong: “the initial range of 0.10% (Batch B1, Month 0)” three times, when the initial range was 0.10–0.12%, and initial results said to include a Month 6 value. The 7 misleading: two different batches' results presented as one change, a Month 0 result placed “at the last time point”, results said to range from the first to the last range while a lower result existed, and “the condition being out of specification”. The pass mark was none wrong, so this failed. Seven checks were added. Run on those paragraphs (placeholders rebuilt from the finished text), they now reject all 11 wrong or misleading ones and 24 of the 30 awkward ones, and none of the 61 ok ones. That is not a fresh test, because the fixes were made after seeing these drafts. The labelled file is `audit_labelled.csv` in the outputs folder for a person to verify.

**Second audit, with the new checks.** 160 drafts, 116 accepted (72%). Read against the data table by Claude: 92 ok, 20 awkward, 4 misleading, 0 wrong. The pass mark (none wrong in at least 100 accepted) was met. Zero wrong in 116 still allows a true wrong rate of up to 2.5% (95% bound). The 4 misleading paragraphs exposed three more gaps: “decreased from the 100.5% (Batch B3) to the 97.6% (Batch B2)” (the word “the” hid the check), “remaining between” the first and last range while a lower result existed, and “Dissolution at 25°C” with the test name cut short. These are closed and tested, and the new checks reject all 4 and none of the 92 ok paragraphs. The fixes were made after seeing these drafts, so a third audit is the fresh test. Each round has found new wording gaps, so expect a smaller but non-zero number of them in the next one.

**What this does not prove.** Planted errors come from the author of the checks, and the first audit showed that is not enough: the model made errors nobody planted. The fair test is the model's own mistakes: 20 drafts for each of the 8 sections with no early stop (`--audit 20`), every accepted paragraph read beside the data table. Pass mark: at least 100 accepted paragraphs and none wrong. The third audit, with the closed gaps, has not been run yet. Not covered: a wrong value in the fact store, a true but unhelpful choice (the lowest result when the highest matters), size words such as “slightly”, and a test name in the middle of a sentence. Stricter checks reject more real drafts, so the acceptance rate has to be measured again. Specification and clinical-narrative sections need their own role and test word lists: the method carries over, the lists do not.

**Test 2: numbers written in words, in the CDISC pilot study report.** The 35 narrative pages of this real 492-page report contain about 1,100 digit strings (results, but also table and section numbers and dates). A digit-only validator would also miss 6 distinct results written only in words (“three laboratory analytes”, “two of the deaths”, “Nineteen of the 30 analytes”), 4 written as words plus digits where only the digits get checked (“Eighty-six (86) subjects”), and 5 distinct “none” or “no” statements with no number at all (“None of the deaths were judged related to treatment”). Counting the synopsis repeats, that is 7, 4 and 8. These are some of the most important sentences in a safety section.

**Test 3: independent routes, in the CDISC pilot data.** CDISC's subject-level ADaM dataset and the one in the R Consortium's FDA pilot package were compared: 254 subjects, 45 shared variables, 0 different values. They are copies: the R Consortium took its ADaM data from PHUSE's re-release of the CDISC pilot, renaming one variable, replacing another and adding a third. Their agreement shows only that the copy is faithful, not that the values are right. Re-deriving from the SDTM data instead reproduced the report's headline facts exactly: 86, 84 and 84 patients randomized; 118 completing Week 24 (60, 28, 30); 110 completing the study (58, 25, 27); 3 deaths (2 placebo, 1 low dose); 111 men and 143 women; mean age 75.1 years (SD 8.25).

**Planted errors in Test 3.** Subject by subject, the SDTM sets equal the ADaM flags for Week 24 completion, study completion and death. Errors were then planted in an in-memory copy of those flags (no file was changed). Comparing subject by subject with SDTM caught all 762 single flipped flags and all 520 swaps of two patients within one arm; comparing only the counts per arm caught none of the swaps. Re-counting the ADaM flags themselves catches none of either, by definition.

**A definition trap.** SDTM counts 230 White patients (218 not Hispanic, 12 Hispanic), while the report says “218 (86%) Caucasian” and lists Hispanic as a separate group, because its case report form used different categories. A check that matches “White” with “Caucasian” by name raises a false conflict; one that knows each number's definition explains it.

**Already right.** Two parts of the design already followed the rule: the ledger anchors its latest hash outside the database, so the database never vouches for itself (section 18), and failed verifications go to a person instead of being retried until they pass (section 14).

**Limits.** Test 1 measures the old check, not the fix. Test 3 shows that the SDTM route for check 4 reproduces the report and catches planted flag errors. But SDTM is also built by the sponsor, so an error made when collecting or mapping the data would be shared by both routes. Its Week 24 count also used visit 12 alone; that matched only because all 118 patients were also in the efficacy population, which the report's definition requires. Only one part of fix 1 holds by construction: the model never types a digit. The binding checks (tested with planted errors on the stability writer, above, but not yet with the model's own mistakes), number words, quantifier words, fix 2 (unknown lineage must count as a copy) and fixes 3 and 5 to 10 still have to be measured, in the seeded-error study of section 36, with errors from outside the team. The three scripts (tracing.py, s2\_number\_words.py, s3\_rederive.py) and their results are in the checks\_stress\_test folder, next to the OCR stress test.

## 31. Roadmap and exit criteria

The overview plans four 8-week phases, 32 weeks from empty cloud account to a validated production pilot on a real IND or BLA. Building a thin working slice in that time is plausible; connecting three live enterprise systems, completing formal validation and piloting a full Module 3 in 32 weeks is not. The order is also backwards: the review screen and validation come last, when they should shape everything from week one.

**The overview's phases and exit criteria, judged:**

| Phase (weeks) | Delivers | Exit criterion | Problem | Better criterion |
| --- | --- | --- | --- | --- |
| 1. Foundation (1–8) | One customer VPC in one commercial region, MCP servers for Veeva, LIMS, ELN, audit ledger | Queries across all three in under 500 ms | Speed is not the risk; access to a customer's Veeva and LIMS alone depends on their IT and security review | Every record of a reference study retrieved; counts and checksums match a manual export |
| 2. Ingestion (9–16) | VLM table extraction, Neo4j schema, Pinecone hybrid search | >99.5% extraction accuracy on 2,000 CoAs | Undefined unit; still \~1 error per 200-value CoA | Zero **undetected** errors on a held-out set: every wrong value flagged or caught; plus reviewer minutes per document |
| 3. Agents (17–24) | LangGraph supervisor, Python sandbox, Claude + R1 | Zero calculation errors on 500 stability matrices | Trivially true for deterministic code | Library outputs match an independent reference (JMP/SAS) on edge cases: missing points, "\<LOQ", rounding ties, non-poolable batches |
| 4. UX + validation (25–32) | Dual-pane UI, GAMP 5 validation, pilot filing | Full Module 3 in under 48 hours with 100% human sign-off | Machines may finish in 48 h; humans verifying thousands of values will not | End-to-end cycle time **including review** vs the manual baseline, and errors caught in a seeded-error study |

**Why the order is backwards:**

- **Validation is a lifecycle, not a final phase.** Under GAMP 5 (ISPE, 2nd edition 2022), user requirements, risk assessment and the test strategy are written at the start and drive the design. Formal validation of a new GMP system commonly takes months on its own. FDA's Computer Software Assurance guidance (final, September 2025) promotes risk-based, lighter-weight testing; it was written for medical-device makers, but pharma widely borrows its approach.
- **The review screen is the product.** Users judge the system by it, and its needs (fact IDs, source boxes, review states) define the data model underneath. Build a thin version first.

**A more realistic roadmap, as vertical slices:**

1. **Setup:** sign a design partner; write user requirements and a risk assessment; build a golden test set from their real, anonymized documents; pick one section.
2. **Slice 1, structured data only:** 3.2.P.8.3 stability tables from LIMS exports → staging and checks → fact store → statistics library → table + narrative with fact placeholders → review screen → ledger. No scans, no live connectors yet.
3. **Slice 2, scans:** add CoA parsing with the OCR + VLM cross-check, and 3.2.P.5.4 batch analyses.
4. **Slice 3, consistency:** the cross-section checker (3.2.S vs 3.2.P vs Module 2.3) and live MCP connectors.
5. **Shadow mode:** run on a real filing **in parallel** with the manual process and compare errors found and hours spent, while formal validation runs.

Shadow mode is the step that turns a demo into evidence a QA head will accept.

### The platform roadmap beyond Module 3

Build outward from Module 3, one module at a time, with the evidence graph from day one:

1. **Module 3 + 2.3** (sections 10–20). Evidence graph and ledger built here, even though only CMC uses them at first.
2. **Module 4 + 2.4/2.6.** SEND data and GLP reports. The smallest data step; Weave's own entry point (nonclinical summaries) shows the demand.
3. **Module 5 + 2.5/2.7.** CDISC datasets, output tables, CSR drafting, patient narratives, re-derivation of key results.
4. **Cross-module consistency and labeling.** Consistency rules across modules, label claim matrix, change propagation.
5. **Module 1, multiple regions, pre-publishing checks**, with hand-off to existing publishing tools.
6. **After submission.** Regulator questions, commitments, post-approval change packages.

Each phase ends with a seeded-error study and a shadow run against a real team's manual work, as described above.

## 32. Future scope and market

Of the three expansion ideas, post-approval impact analysis is the strongest and closed-loop bioreactor control the weakest. The $8.4B market figure has no source and is probably inflated for software alone.

**The three expansions, judged:**

| Idea | What it means | Strength | Problem | Verdict |
| --- | --- | --- | --- | --- |
| Closed-loop bioreactor optimization | When stability data trends badly, recommend changes to feed strategy or harvest timing, connected to the MES | Big value if it worked | Stability results arrive months or years after the batch was made, too late to steer it. Process changes need change control and often prior regulator approval. Draft EU Annex 22 says LLMs should not be used in critical GMP applications | Weakest. A different product (process analytics) needing validated static ML models with human approval, not LLMs |
| Multi-agency translation (FDA → EMA, PMDA, NMPA) | Re-format a validated US Module 3 for other regions | Module 3 is already harmonized (ICH M4Q), so the fact store can be reused almost as is | The real differences sit in Module 1, 3.2.R, pharmacopoeia references (USP vs Ph. Eur. vs JP), and language (Japanese, Chinese). Needs EU and Asia deployments, which GovCloud blocks | Natural extension |
| Post-approval impact agents | A change is proposed (swap a filter supplier); find every affected product license worldwide and draft the variation filings | Recurring, continuous work; the graph's impact analysis (section 13) does exactly this; aligns with ICH Q12 lifecycle management | Registration data lives in RIM systems, where Veeva is the incumbent | Strongest. Likely the best business, possibly via partnership |

**Check: the market size.** The overview's "$8.4 billion addressable market across regulatory management software and services" has no source. For comparison, Grand View Research [projects the regulatory information management software market at $5.11 billion by 2033](https://www.grandviewresearch.com/press-release/global-regulatory-information-management-rim-system-market) (9.1% annual growth from 2026). The $8.4B probably adds outsourced regulatory services. A credible pitch builds the number **bottom-up** instead: target companies × CMC submissions per company per year (INDs, NDAs/BLAs, supplements) × price per submission or per product. Each input can be researched and defended.

**Fix:** build the number bottom-up: target companies × CMC submissions per company per year × price per submission. FDA's [PDUFA dashboards](https://www.fda.gov/about-fda/fda-track-agency-wide-program-performance/fda-track-prescription-drug-user-fee-act-pdufa-performance-dashboards) count original NDAs and BLAs and the manufacturing supplements that need prior approval. Cross-check top-down against the $5.11 billion RIM software forecast above.

**Who buys, and how:**

- **Economic buyer:** head of Regulatory CMC or VP Regulatory Affairs.
- **Must approve:** QA (validation), IT security (the deployment), sometimes legal (data rights with CMOs).
- **Channel:** small biotechs outsource regulatory writing to CROs and consultancies, which can be partners. Weave Bio's work with Parexel shows the pattern.
- **Beachhead:** mid-size biotechs that file often and rely heavily on CMOs. They have the most scanned CoAs, feel the pain most, and decide faster than big pharma.
- **Sales cycle:** long. Security review, validation and a shadow-mode pilot come before any production use.

**Competitors** are listed in section 5. The positioning that survives them: verification and provenance first, drafting second.

## 33. How this differs from Weave Bio and the others

Weave Bio is **drafting-first with traceability**: it writes documents and links each sentence back to a source paragraph. This platform is **evidence-first**: it builds a verified graph of facts and claims, and documents are views of it. That is a different architecture, not a copy, and it targets the part buyers worry about most: proving the dossier is right and keeping it right.

**Against Weave Bio, using only what it has published:**

| Capability | Weave Bio (public information) | This platform |
| --- | --- | --- |
| Scope | IND drafting incl. nonclinical summaries; NDA workflow launched with Parexel ([April 2026](https://www.businesswire.com/news/home/20260429322286/en/Weave-Bio-Launches-NDA-Workflow-Designed-in-Partnership-with-Parexel-Extending-AI-Native-Platform-Coverage-Across-the-Full-Regulatory-Lifecycle)); regulator question workflows; Takeda across 14 programs | All modules plus labeling, multiple regions and post-approval lifecycle |
| Traceability | Sentence-level tracing to sources; “always-current links” and Data Tags reuse values across a document set | Each value mapped to its exact cell, dataset row or page box; claims typed and linked to evidence sets |
| Number checking | Automated verification of critical data and 95% source fidelity reported, yet its own study found misread values (section 34) | Deterministic validator: every number bound to the right fact; key results re-derived from the collected (SDTM) data, not the sponsor's derived datasets |
| Cross-module consistency | AutoReview flags inconsistencies, omissions and conflicts; how it works and how far it reaches across modules is not published | Explicit consistency rules across modules, label and regions, with change propagation |
| Structured data | Not described beyond structured eCTD outputs and DOCX export | Native SDTM, ADaM, SEND, Define-XML; ready for M11/USDM, M4Q(R2) and eCTD v4.0 IDs |
| Compliance evidence | Audit trail of every edit, comment and version; role-based permissions; SOC 2 Type II | Part 11 hash-chained ledger, frozen and versioned prompts, a credibility file per AI use |
| Openness | Pulls source files from Veeva and resyncs them; other integrations not described | MCP connectors and A2A hand-offs; works alongside Veeva |

**The others, in one line each:** Celegence and SyncIQ focus on CMC and Module 2.3 (SyncIQ sells cross-module 2.3/3 consistency, a narrow version of section 8). Peer AI uses specialized agents across preclinical, clinical and CMC documents. Veeva owns the document platform and plans agentic authoring for late 2027. All of them lead with faster drafting.

**Honest caveat:** Weave has paying customers, real data and a CRO partner; this is a design. The differences in the table are claims until a benchmark proves them. The benchmark to build is a **seeded-error study**: plant known mistakes across modules (a wrong number in 2.7.3, a dose that differs between the label and a CSR, an outdated shelf life in 2.3) and measure how many each approach catches. Catching nearly all of them is the pitch.

**One-line positioning:** "Other tools write your dossier faster. This one proves every claim in it, across every module and region, and keeps it proven as the data changes."

## 34. Product experience: learning from Weave Bio, and going further

**What this is based on.** Weave's app sits behind an enterprise login, so only its customers can use it. This section works from the product screens Weave itself publishes on its Submission Builder page (four stylised screenshots and a 15-second animation of the editor, examined frame by frame), its product and security pages, plus the AutoIND study that Weave and Takeda authors published (arXiv 2509.09738), which measured how much of the AI's drafts an expert assessor had to fix. Treat the screen details below as Weave's own published renderings of its product, not hands-on use.

**The strategy in one line:** match everything Weave has made standard, then win where its own study shows gaps: proof you can see, review by exception, and drafts that need less rework.

### What Weave's product screens show

Weave's Submission Builder page shows its product in four stylised screenshots and a 15-second animation of the editor. These are the patterns they contain, and how our app keeps the same layout and adds to it.

| Weave screen | What is on it | Our version: same layout, plus |
| --- | --- | --- |
| Program bar | Program code (WEA-123), then tabs Data room, US IND, Editor. One data room feeds several submissions (US IND, EU CTA, US NDA) | Same bar: program, Data room, Dossier, Review queue, Consistency, Editor. Region chips (US NDA, EU MAA) switch between overlays of one core dossier |
| Data room files | Tabs Overview, Files, Explore; search by name, data tags or metadata; a synced “Veeva source files” folder; a file table with checkboxes | Same, plus each file shows how many facts were extracted from it, their verification state, and which sections use them |
| Dossier | Tabs Dossier, Detailed status, Additional documents; search by document number or title; “+ Add content”; a collapsible eCTD tree (Module 1, Module 2 with 2.2 to 2.5, then 2.6 and 2.7) | Same tree, plus status, proof score and open conflicts on every row (drawn below) |
| Editor | Section title (2.6.6 Toxicology written summary); modes Editing, Generate all content, Fill variables; collaborator avatars; a side panel with an AI comment (“lacks critical content in subsections…”) and a suggestion shown as a tracked change (delete “8–12 weeks”, add “8–10 weeks”) | Same editor and side panel, plus fact chips instead of typed numbers, a required-elements checklist, the source page beside the text, and a length budget (the section workspace below) |
| Document canvas | Text set like the final Word file: serif type, numbered headings, ruled tables (“Table 1: Summary of Toxicology Studies”) | Same: what you edit is what gets exported |
| Source check | Sentences tinted green (traced to a source) or underlined red (flagged) in a 2.4.2 Pharmacology section | A state on every value, not just every sentence, and one click opens the exact source cell or page box |
| Look and feel | Deep green brand, one light accent, rounded panels, plenty of white space; sans-serif interface, serif document | Same calm approach in our own colours, with colour kept for status (verified, unverified, mismatch) |

Keeping Weave's layout makes the product familiar to anyone who has seen theirs. The added layers are the reasons to switch.

&#91;embedded content: Dossier view wireframe · Weave-style tree plus proof and conflicts\]

The tree on the left is the same shape as Weave's dossier view, and each row adds a status, a proof score and open issues. Selecting the label row shows the conflict: shelf life is 36 months in Module 3 and the quality summary, but 24 months in section 6.3 of the EU product information (the SmPC, where shelf life is stated). One click fixes it from the source fact, and the card below lists what the last data change touched.

### What Weave Bio does well (now table stakes)

| Pattern | What Weave does | Why it works |
| --- | --- | --- |
| Shaped like the job | Submission Builder follows five steps: author, assemble the dossier, review together, verify sources, export | Writers see their own process, so there is little to learn |
| Templates, not a chat box | Configurable templates with variables, instructions and tables, “grounded in source context” instead of “disconnected prompting” | The structure comes out right every time, and a team sets its house style once |
| Organised by lifecycle stage | Candidate → Pre-Clinical → Clinical → Market → Post-Market, across Program Planner, Submission Builder and HAQ Manager | People find work by where the drug is, which is how regulatory teams think |
| Sources one click away | Sentence-level tracing, “always-current links”, Data Tags for reused values, literature citations | A reviewer checks a claim without leaving the page |
| An automatic second reader | AutoReview flags inconsistencies, omissions and conflicts | Problems surface before a person spends review time |
| Collaboration in one place | Shared workspace with comments, redlines, section status, version restore, an audit trail of every edit, and role-based permissions | Replaces email chains and files named final\_v7 |
| Word as the exit | Customisable DOCX export; source files pulled from Veeva keep their folder structure and resync | Fits the tools publishers and reviewers already use |
| Agency questions as a tracker | HAQ Manager extracts each question, assigns owner, reviewer, approver and due date, finds similar past questions, and drafts only from sources the user explicitly selects | A stressful deadline becomes a visible queue, and explicit source selection stops one program's data leaking into another |
| Trust stated up front | SOC 2 Type II, zero data retention with model providers, per-program data rooms, model updates gated by a regression suite | Answers the first questions every pharma IT and QA team asks |

Do not try to beat Weave on these. A product without them will not get past a first demo, so build them to the same standard and spend the extra effort on what follows.

### Where Weave's own study shows room to do better

In the AutoIND study (two INDs, one blinded assessor), drafting time fell by about 97%, from roughly 100 hours to 3.7 and 2.6 hours, with no critical regulatory errors. But quality scored 69.6% and 77.9%, and the authors write that 10 to 25% of generated content needed revision. The gaps are specific, and each one is a design problem with a design answer.

| Finding | Evidence from the study | Our design answer |
| --- | --- | --- |
| Drafts too long | AI documents were 3 to 5 times longer than human-written ones | A live length budget per section, set from expert examples and shown while writing |
| Methods over results | Emphasis scored 6.7% and 37% in toxicology | Results-first templates, and an emphasis view that tints methods and results differently |
| Required content missing | Toxicology completeness 32% and 59%; 35% of summaries missed essential study-design elements; GLP dose-formulation analysis was omitted every time | A required-elements checklist per section (from ICH M4, E3 and the content plan) that blocks “ready for review” until each item is present or marked not applicable |
| Structure and AI voice | Of 156 clarity comments, 32% were structural and 28% were AI-style phrasing | The outline is approved before any prose is written, and a house-style checker flags AI-style phrasing |
| Wrong numbers | A wrong onset time (11 h instead of 7 h); NOAELs assigned to in-vitro studies | Every number is a fact chip with a verification state, and a mismatch blocks sign-off (section 6) |
| Slow to start | A rival's comparison says onboarding takes weeks of data-room setup (a biased source: it was written by a competitor's founder) | First useful output on day one (principle 7) |
| Hard to try | Enterprise sales only, no public pricing | A free, self-serve consistency check (below) |

### Nine principles for our product

1. **Show proof, do not ask for trust.** Every number and claim carries a visible state: verified, derived, human-confirmed, unverified or mismatch. Each section shows a proof score (“46 of 48 values verified”), so a reviewer sees the risk before reading a word.
2. **Review by exception.** Reviewers work from a queue ranked by risk: mismatches first, then unverified values, then new claims. Verified, unchanged paragraphs are collapsed. The whole queue works from the keyboard.
3. **Outline first, prose second.** The required-elements checklist comes from the guideline and the content plan. The writer approves the outline before drafting, which removes most structural edits before they happen.
4. **Drafts that need less rework.** Length budgets, results-first templates, and prompts tuned against expert edits with GEPA (section 28). Every human edit is kept as a signal for the next round of tuning.
5. **See the consequence of a change.** Changing a fact (a new stability time point, a corrected batch count) first shows every section, table and module it touches, through the evidence graph (section 8). Nothing updates until someone approves the list.
6. **Meet writers in Word.** A Word add-in shows the same fact chips and evidence panel, so writers who never leave Word still get proof and checks.
7. **First value in a day.** Connect a folder or Veeva vault, auto-classify documents into the eCTD tree, generate a content plan, and return a consistency report on the first day, before any drafting.
8. **Compliance that feels normal.** Part 11 signatures state their meaning (“approved as author”), re-authentication happens only at signature, the audit trail reads as a plain-language timeline, and every source carries a coloured program badge so reuse across programs is visible at once.
9. **One screen per role.** The writer, reviewer, CMC lead, regulatory lead and publisher each start on the view their job needs, not one generic dashboard.

### The section workspace

&#91;embedded content: Section workspace wireframe · outline, draft with fact chips, evidence\]

The writer drafts in the centre, where every number is a chip coloured by its state. Clicking the red 100.4% chip opens its evidence on the right: the source page with the value boxed, the source value (100.2%), and one-click fixes. The checklist on the left shows what the section still needs, and the proof score in the top bar is what the reviewer sees in their queue. This screen is where sections 6, 8 and 17 become something a person touches.

### Six key screens

| Screen | Main user | What it shows |
| --- | --- | --- |
| Dossier view | Regulatory lead | Every module and section with status, proof score, owner and due date, blockers first |
| Section workspace | Writer | Outline and checklist, draft with fact chips, evidence panel (drawn above) |
| Review queue | Reviewer, QA | Risk-ranked items across sections; accept, fix or send back with a reason |
| Consistency map | CMC and regulatory leads | Conflicts across modules from the evidence graph, such as a shelf life that differs between Module 2.3 and 3.2.P.8 |
| Question board | Regulatory lead | Agency questions as cards with owner, due date, linked evidence and draft answer |
| Onboarding wizard | Admin | Connect sources, map folders to the eCTD tree, set roles, run the first consistency check |

### Using the experience to win customers

Weave sells to enterprises through demos and pilots. We can add a self-serve door: a free consistency check where a team uploads two documents, for example a Module 2.3 summary and a 3.2.P.8 stability report, and gets back every mismatch with page references. Files are processed in isolation and deleted after the report. It shows the core value, proof, in the first few minutes, and every report is a lead for the full platform.

### How we will measure it

| Metric | Our target | Why it matters |
| --- | --- | --- |
| Time to first useful output | Under one day from connecting sources | Tests principle 7 |
| Reviewer minutes per section | Falls with every release | Tests review by exception |
| Rework rate | Below the 10 to 25% in Weave's study | Share of generated text that reviewers change |
| Length against expert examples | Within 20% either way | The study found drafts 3 to 5 times too long |
| Seeded-error catch rate | 100% of planted wrong numbers, including errors written outside the team | Shows the fact checks work |
| System Usability Scale (SUS) | Above 70 in pilot tests | A standard 10-question usability score; 68 is average |

## 35. Scorecard: every issue in the overview, with its fix

43 issues: 8 high, 21 medium, 14 low. The high ones cluster in two places: numbers that still pass through the model, and the pharmaceutical science in the worked example. Section numbers in brackets point to the full explanation.

| # | Severity | Topic | Overview says | Fix (section) |
| --- | --- | --- | --- | --- |
| 1 | High | Math script | The model types data values into the Python script | Load values by fact ID; the model types none (6, 16) |
| 2 | High | Provenance | The model emits the provenance JSON (page, box) | The system attaches provenance from the fact record (6) |
| 3 | High | OOT test | Fits the line through the point it tests; flags only at 0.164% or more | Prediction interval from earlier data flags above \~0.124% (16) |
| 4 | High | Sample output | "Month 36 under accelerated conditions" | Accelerated runs 6 months; Month 36 is long-term 25°C/60% RH (20) |
| 5 | High | Sample output | Total degradation products compared with a Q3B threshold | Q3B thresholds are per individual product; totals follow the product's own spec (20) |
| 6 | High | Guideline choice | ICH Q3B applied in a BLA story | Q3A/Q3B exclude biologics; use Q6B/Q5C, chosen by modality (2, 20) |
| 7 | High | Sovereignty | Pinecone Serverless, Neo4j Aura, OpenAI embeddings in a "single-tenant VPC" | Self-hosted vector, graph and embedding models inside the VPC (13) |
| 8 | High | Sovereignty | Claude Opus 4.6 inside the customer's region | Not on AWS's GovCloud Bedrock list; check the chosen region's Bedrock list and use a model it lists (15) |
| 9 | Medium | Sample output | Q3B 0.20% threshold with no daily dose | Compute the threshold from maximum daily dose (20) |
| 10 | Medium | Data sanity | Batch 2024-12 has Month-36 data | Impossible before Dec 2027; add a date rule (20) |
| 11 | Medium | Business impact | One decimal error triggers Refuse-to-File | RTF is for incomplete applications; expect an IR or CRL questions (3) |
| 12 | Medium | Agents | HIPAA / PII redaction agent | CMC rarely holds patient data; reframe as confidentiality redaction (14) |
| 13 | Medium | Sandbox | "PyChain WASM" runtime | Does not exist; Firecracker microVMs plus a validated statistics library (16) |
| 14 | Medium | Models | DeepSeek-R1 does "preliminary data parsing" | R1 is text-only; it cannot read scans (15) |
| 15 | Medium | Models | R1 on "isolated H100 nodes" | \~700 GB at FP8 exceeds one 8×H100 node; multi-node or a smaller model (15) |
| 16 | Medium | Models | DeepSeek-R1 as the local model | Outdated (V4 shipped Apr 2026) and flagged in security reviews; consider gpt-oss, Llama, Mistral, Granite (15) |
| 17 | Medium | Deployment | AWS GovCloud as the default | Commercial region per customer; GovCloud only for government programs (19) |
| 18 | Medium | Parsing | VLM reads peak areas off chromatogram charts | Take numbers from Empower or the printed results table (12) |
| 19 | Medium | Parsing | VLM-generated bounding boxes as audit provenance | Boxes from the OCR layer or table grid, values from two blind reads (12) |
| 20 | Medium | Long context | 1M tokens removes chunking; ingest 50,000 pages | 1M tokens is \~1,500–3,000 pages; use table-aware chunking and the fact store (13, 15) |
| 21 | Medium | Math | "100% mathematical accuracy" | True of arithmetic only, not of inputs, methods or rounding (16) |
| 22 | Medium | Agents | Compliance Audit as an agent | Logging must be automatic at framework level (14) |
| 23 | Medium | Agents | No consistency checker, no writer node | Add both; cross-section mismatches are the top error source (14) |
| 24 | Medium | Regulatory logic | Limits justified by other products' past filings | Justify with this product's data, safety and guidelines (20) |
| 25 | Medium | Exit criteria | 500 ms latency, >99.5% accuracy, zero calc errors, 48 h compile | Completeness checksums, zero undetected errors, reference comparison, cycle time with review (31) |
| 26 | Medium | Roadmap | 32 weeks, validation and UI last | Validation from week one, vertical slices, shadow mode (31) |
| 27 | Medium | Competition | Existing solutions = Veeva, MasterControl, OCR | Celegence, SyncIQ, Weave Bio, Peer AI, Veeva AI roadmap (5) |
| 28 | Medium | Regulation | No mention of AI-specific rules | FDA draft AI guidance (2025), FDA–EMA principles (2026), EU draft Annex 22 (18, 30) |
| 29 | Medium | Ledger | Hash chain alone makes the log immutable | Add external anchoring, insert-only role, entry signing (18) |
| 30 | Low | Business impact | Delay costs $1–3M per day | Average \~$0.8M/day (Tufts 2024); $1M+ only for large drugs (3) |
| 31 | Low | Business impact | IR or RTF halts the clock 30–90 days | IRs do not stop the clock; a major amendment adds 3 months (3) |
| 32 | Low | Regulation | Traceability comes from Part 11 | Also 21 CFR 211 and FDA data-integrity guidance (4) |
| 33 | Low | Source systems | Empower has no API hooks | The Empower Toolkit exists; lab-data platforms use it (4) |
| 34 | Low | MCP | MCP replaces custom glue code | The glue moves inside each MCP server (11) |
| 35 | Low | Orchestration | LangGraph v0.3+ | LangGraph 1.0 shipped Oct 2025 (14) |
| 36 | Low | Orchestration | Checkpoints in Redis | Postgres checkpoints, hashed into the ledger (14) |
| 37 | Low | Deployment | "Part 11 compliant" infrastructure | Compliance is the system plus procedures, validated by the customer (19) |
| 38 | Low | Deployment | Nitro Enclaves for isolation of inference | Enclaves suit CPU work such as keys, not GPU inference (19) |
| 39 | Low | Deployment | Tenant memory isolation in a single-tenant design | Pick one tenancy model and word it consistently (19) |
| 40 | Low | History | "LangChain 2021" | LangChain launched Oct 2022; LangGraph Jan 2024 (27) |
| 41 | Low | eCTD | 3.2.P.5.5 for a stability narrative | Belongs in 3.2.P.8.3, supporting 3.2.P.5.6 (20) |
| 42 | Low | eCTD | Diagram shows 3 modules, no 3.2.R | 5 modules; include 3.2.R regional (2) |
| 43 | Low | Numbers | $8.4B market, 12,000 hours, "60% scanned" | Unsourced; build bottom-up or cite (3, 32) |

## 36. If you build it: a realistic student-scale version

You cannot get access to a real Veeva, LIMS, GovCloud or H100 cluster, and you do not need them. A focused version that proves the core principle (facts first, every number verified and traceable) is more impressive than a shallow copy of the whole enterprise diagram.

**Scope:** real public data only. The only invented things are errors planted on purpose, in copies, to measure the checker. Three real sources carry the build: a manufacturing dataset for the data engine, one approved drug's public documents for the dossier audit, and an open clinical-trial dataset for the clinical slice.

**Real data, by job** (each source checked for access and licence in October 2026):

| Job | Real dataset | What it gives | Access and licence | Limits |
| --- | --- | --- | --- | --- |
| Batch analyses (3.2.P.5.4), raw-material tests, the OCR stress test | [Lek Pharmaceuticals (Sandoz) production data](https://www.nature.com/articles/s41597-022-01203-x), Scientific Data 2022 | 1,005 production batches of a cholesterol-lowering film-coated tablet in 4 strengths (Nov 2018 to Apr 2021): dissolution mean and minimum, total impurities, impurities O and L, residual solvent, API and excipient tests, tablet-press signals every 10 seconds | Open download from figshare, CC BY 4.0 (credit the authors) | Product name hidden; no final-product assay, no specification limits, no stability data |
| Specifications, stability design, shelf life, storage (3.2.P.5, 3.2.P.8) | FDA chemistry reviews in Drugs@FDA, and EMA EPARs | For Kerendia: 10 and 20 mg tablets, 36-month expiry, long-term storage at 25°C/60% RH and 30°C/75% RH for 36 months, accelerated 40°C/75% RH for 6 months, HDPE bottles of 30 and 90 | FDA reviews: open PDFs (US government work). EPARs: free to read, EMA copyright | Numeric results and most limits are redacted as trade secrets (Kerendia: 75 + 39 pages withheld) |
| Clinical overview, summaries, study reports (2.5, 2.7, 5.3) | [Health Canada Public Release of Clinical Information](https://clinical-information.canada.ca/) (685 drugs listed); [EMA clinical data portal](https://clinicaldata.ema.europa.eu) as backup | Full study reports with protocol and statistical analysis plan | Health Canada: click-through, non-commercial use; link to the files rather than re-hosting them. EMA: account needed; download only on the academic tier | No patient-level listings |
| Patient-level datasets (SDTM, ADaM) | [CDISC Pilot 01](https://github.com/cdisc-org/sdtm-adam-pilot-project), used in the R Consortium FDA pilot submissions | A real phase II trial of transdermal xanomeline in Alzheimer's disease (Eli Lilly, 254 patients, de-identified): SDTM, ADaM, define.xml and a 492-page study report | Free on GitHub; CDISC terms require credit and forbid altering the data | This transdermal xanomeline product was never approved (oral xanomeline with trospium was, as Cobenfy, in 2024), so there is no matching label to cross-check |
| Labels | [DailyMed](https://dailymed.nlm.nih.gov/dailymed/spl-resources.cfm) (SPL XML) and openFDA | Current structured US labels with every past revision; the EU SmPC is published with each EPAR | US labels: public domain. SmPC: EMA copyright | Text is submitted by the company |
| Regulator feedback | [openFDA complete response letters](https://open.fda.gov/apis/transparency/completeresponseletters/) | 458 FDA rejection letters with full text (as of 13 Aug 2026), to build the deficiency rule library | Public | Trade secrets redacted |
| Real CoA layouts for the parser | Supplier Certificates of Analysis (Sigma-Aldrich lot CoAs, BioSpectra excipient CoAs) | Real layouts and real scans | Site terms bar bulk download and reuse: fetch a handful by hand, for testing only | Not a dataset |
| Retrieval corpus | ICH guideline PDFs (M4Q, Q1A(R2), Q1E, Q3B(R2), Q6A) | The rules themselves | Public | None |

**The one gap:** no public dataset has real stability results over time (assay and impurities at each time point), because those stay inside companies. The shelf-life code is therefore validated against an independent implementation in R (for example the expirest package), and the stability section is demonstrated on the stability design and conclusions that FDA reviews do publish.

**The anchor drug: Kerendia (finerenone) tablets.** Every public piece exists for it: the FDA chemistry review (NDA 215341, 2021), the EPAR, Health Canada's clinical documents and the current US label. Verquvo (vericiguat) and Paxlovid are the alternates. Kerendia even holds a real version difference: the 2021 review covers 10 and 20 mg tablets, while the label revised in July 2025 also lists 40 mg. The system must tag every fact with the document version it came from.

**Errors planted on copies, for testing only:** decimal shifts (0.14 vs 0.014), unit swaps, a dropped “<” sign, a value bound to the wrong batch, a value that differs between two documents, an impossible date, an overclaim such as “no new safety signals”. Each one is logged in a key file so the catch rate can be measured. So that the test does not only find what the builder imagined, part of the errors come from outside: deficiencies described in real FDA complete response letters, the misreads from the OCR stress test, and a classmate who has not read the checker code (section 30). Errors go into copies of drafts and rendered pages, never into the CDISC files, whose terms forbid altering the data.

**Stack (free or cheap):**

| Layer | Choice | Why |
| --- | --- | --- |
| Fact store + vectors + keyword search | PostgreSQL with pgvector and full-text search | One database, exact types, easy to explain |
| Lineage graph (optional) | Neo4j Community in Docker | Shows the graph idea for genealogy and impact queries |
| PDF / OCR | PyMuPDF for digital PDFs; Docling or PaddleOCR for scans | Word boxes for provenance |
| Vision + drafting model | Claude API (a Sonnet-class model for cost) | Vision, structured output, good writing |
| Workflow | LangGraph 1.x, Postgres checkpointer, an interrupt for human review; steps written as plain functions and wrapped in Temporal once the first human wait appears | Shows durable state and human-in-the-loop |
| Connectors | Two small MCP servers with the official Python SDK: "LIMS" over your CSV/Postgres, "DMS" over a folder of PDFs | Demonstrates MCP honestly |
| Statistics | A small library on NumPy, SciPy, statsmodels, with pytest tests and `Decimal` rounding | ICH Q1E shelf life, prediction-interval OOT |
| Review screen | React + PDF.js + Tiptap editor with fact chips | Click a number, see the box |
| Ledger | Postgres table with a SHA-256 hash chain and a verify script | Demo: edit a row by hand and watch verification fail |

**Metrics that make it convincing:**

1. Extraction accuracy on scanned tables rendered from the real batch values, and the share of wrong extractions that were **flagged** (target: all).
2. Share of injected errors caught, reported separately for errors the builder wrote and errors from outside (section 30).
3. Statistics matching an independent reference (statsmodels vs your library, or R).
4. Unverifiable numbers in final drafts, counted by re-reading the exported files with an independent parser: must be zero.
5. Tamper detection: the ledger check finds a manual edit.

**Build order:**

1. Loaders for the real sources (the Lek CSV, Drugs@FDA PDFs, DailyMed XML) + fact schema.
2. LIMS path end to end: CSV → staging and checks → facts → statistics → stability table.
3. Drafting with fact placeholders + the number and claim validator.
4. Review screen with click-to-source.
5. Scanned CoA parsing with the OCR + VLM cross-check.
6. Ledger, LangGraph wiring, MCP servers.
7. Evaluation report with the five metrics.

**How to pitch it in one breath:** "An AI system for pharmaceutical regulatory dossiers where the language model never produces a number: every value comes from a verified fact store, is computed by tested code, links to its exact source cell, and is logged in a tamper-evident ledger. It even catches the science errors in the original design spec."

### The whole-eCTD student version: one real drug, two data engines

Once the Module 3 slice above works, the right demo is not “all of eCTD” but **one real drug audited across modules by the consistency engine** (section 8), plus two data engines on open data. That shows the moat in a way no single-module tool can.

| Part | Real public data | What you build |
| --- | --- | --- |
| Consistency audit: Kerendia across Module 3, Module 2.7, Module 5 and the label | Kerendia's FDA chemistry review and EPAR (Module 3 facts), Health Canada's Kerendia study reports (clinical claims), the US label from DailyMed and the EU SmPC published with the EPAR | Extract facts and claims from every document into one graph; check strengths, storage, shelf life, dose and patient numbers across them; build the label claim matrix (sections 3, 6, 14 and 16) |
| Module 3 data engine | The Lek batch data (above) | Fact extraction, statistics library, the batch-analysis table (3.2.P.5.4) and the OCR stress test (section 12) |
| Module 5 data engine | CDISC Pilot 01: SDTM, ADaM and the study report from CDISC's pilot project, plus the [R Consortium Pilot 1 submission package](https://github.com/RConsortium/submissions-pilot1-to-fda), with define.xml, the analysis data reviewer's guide and R programs for the output tables | Read the output tables, re-derive headline numbers from SDTM rather than ADaM (section 30), and draft a CSR results paragraph and a 2.7.3 paragraph with placeholders |

**The real-world check first:** run the audit on Kerendia's public documents as they are. The system should notice that the 2021 FDA review covers 10 and 20 mg tablets while the July 2025 label adds 40 mg, and record that as a version difference with both sources, not as an error. The storage statement in label section 16 should agree with the storage recommendation in the review, and every patient number in label section 14 should trace to a study report.

**The demo that sells it:** plant one wrong number in a copy of a drafted Kerendia section (never in the source files themselves) and show the platform (1) flag the mismatch against the other Kerendia documents, (2) list every affected placement, and (3) update the placeholders and queue the prose for re-review, with every step in the ledger. Then run the seeded-error study across all three parts and report the catch rate.

**What to add to the stack above:** a CDISC reader (pyreadstat or pandas for .xpt files, plus a define.xml parser), the evidence graph as Postgres tables plus Neo4j Community for placements and propagation, and one Agent Skill per document type (stability section, CSR results, label section).

## 37. Glossary

Every acronym in the two overview docs and this explainer, in plain words. Watch out for **API**, which means two different things in this project.

| Term | Meaning |
| --- | --- |
| ALCOA+ | Data-integrity standard: Attributable, Legible, Contemporaneous, Original, Accurate, plus Complete, Consistent, Enduring, Available |
| API (pharma) | Active Pharmaceutical Ingredient, the drug substance |
| API (software) | Application Programming Interface |
| BLA | Biologics License Application, to market a biologic in the US |
| Blind read | A second reading of a cell made without seeing the first reading, so the two can fail independently |
| BM25 | Standard keyword-ranking formula used in search engines |
| CDER / CBER | FDA's drug center / biologics center (vaccines, blood, cell and gene therapy) |
| CDS | Chromatography Data System, such as Waters Empower |
| CFR | Code of Federal Regulations; Title 21 covers food and drugs |
| cGMP / GMP | (current) Good Manufacturing Practice, the legal quality rules for making medicines |
| CMC | Chemistry, Manufacturing and Controls |
| CMO / CDMO | Contract (Development and) Manufacturing Organization |
| CoA | Certificate of Analysis, one batch's test results against its specification |
| Common-mode error | Two checks failing the same way at the same time, so their agreement hides the error |
| CRL | Complete Response Letter: FDA's "not approved yet, here is why" |
| CSV / CSA | Computer System Validation / FDA's risk-based Computer Software Assurance approach |
| DMS / RIM | Document Management System / Regulatory Information Management (Veeva Vault RIM) |
| Double programming | Two programmers produce the same table independently, without seeing each other's code, and the outputs are compared |
| eCTD | electronic Common Technical Document, the 5-module dossier format |
| ELN | Electronic Lab Notebook (Benchling) |
| EMA / PMDA / NMPA | Regulators of the EU / Japan / China |
| ERP / MES | Enterprise Resource Planning (SAP) / Manufacturing Execution System |
| ESG | FDA Electronic Submissions Gateway |
| FedRAMP | US government cloud security authorization program |
| FIPS 140-3 | US government standard for validated cryptographic modules |
| GAMP 5 | ISPE's industry guide to validating computerized GMP systems |
| GovCloud | AWS regions isolated for US government workloads |
| HPLC | High-Performance Liquid Chromatography, separates a sample into measurable peaks |
| HSM / KMS | Hardware Security Module / AWS Key Management Service, which keeps encryption keys |
| ICH | International Council for Harmonisation, writes the Q (quality) and M (format) guidelines |
| IND | Investigational New Drug application, to start human trials |
| Independence rule | This project's test for any check: it must be able to fail, so it needs its own input, must test meaning as well as value, and must be graded by tests its builders did not write (section 30) |
| IR | Information Request from FDA during review |
| JWT / OIDC / SAML | Login token format / modern single-sign-on protocol / older enterprise single-sign-on protocol |
| LIMS | Laboratory Information Management System |
| Lineage | The record of where a value came from and every copy it passed through |
| LOQ | Limit of Quantitation: below it a value is reported as "\<LOQ" |
| MCP | Model Context Protocol, the standard plug between AI apps and tools |
| MSAT / TechOps | Manufacturing Science and Technology / Technical Operations |
| NDA | New Drug Application, to market a small-molecule drug in the US |
| NMT / NLT | Not More Than / Not Less Than, in specifications |
| OCR / VLM | Optical Character Recognition / Vision-Language Model |
| OOS / OOT | Out of Specification (broke a limit) / Out of Trend (unusual but within limits) |
| PDUFA | Law setting FDA review-time goals and user fees |
| QA / QC | Quality Assurance (audits the system) / Quality Control (runs the tests) |
| QOS | Quality Overall Summary, Module 2.3 |
| RAG | Retrieval-Augmented Generation: search first, then let the model answer from what was found |
| RBAC | Role-Based Access Control |
| RH | Relative Humidity |
| RPA | Robotic Process Automation, bots that replay screen clicks |
| RTF | Refuse-to-File: FDA declines to review an incomplete application |
| SDTM / ADaM | CDISC formats for trial data. SDTM: the collected data in standard tables. ADaM: analysis-ready data derived from SDTM, including population flags (section 22) |
| SmPC | Summary of Product Characteristics, the EU label; section 6.3 states the shelf life |
| Table grid detection | Finding a table's ruled lines so each value can be tied to its row and column |
| TDI | Total Daily Intake of an impurity |
| vLLM | Open-source server for running language models fast on GPUs |
| VPC | Virtual Private Cloud, an isolated network in the cloud |
| WORM | Write Once, Read Many storage (S3 Object Lock) |

## 38. Sources

Pages opened while checking the facts in this explainer, grouped by topic. The two overview docs in this project are the subject being explained.

**Regulation and guidelines**

- [21 CFR Part 11 (eCFR)](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11)
- [21 CFR 314.101, filing an NDA (eCFR)](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-D/part-314/subpart-D/section-314.101)
- [FDA draft guidance: Refuse to File, NDA and BLA submissions (2017)](https://www.fda.gov/files/drugs/published/Refuse-to-File--NDA-and-BLA-Submissions-to-CDER-Guidance-for-Industry.pdf)
- [FDA review clock explained (Assyro)](https://www.assyro.com/blog/fda-review-clock-explained)
- [ICH Q1A(R2) Stability Testing](https://database.ich.org/sites/default/files/Q1A%28R2%29%20Guideline.pdf)
- [ICH Q1E Evaluation of Stability Data](https://database.ich.org/sites/default/files/Q1E_Guideline.pdf)
- [ICH Q3B(R2) Impurities in New Drug Products](https://database.ich.org/sites/default/files/Q3B%28R2%29%20Guideline.pdf)
- [New ICH Q1 draft guideline (ECA Academy)](https://www.gmp-compliance.org/gmp-news/new-ich-q1-draft-guideline-whats-changing-in-stability-testing)
- [ICH revises Q1 guideline (Pharmaceutical Online)](https://www.pharmaceuticalonline.com/doc/ich-revises-q-guideline-advancing-stability-testing-standards-0001)
- [FDA eCTD requirements and v4.0 (IntuitionLabs)](https://intuitionlabs.ai/articles/fda-ectd-requirements-guide)

**AI regulation**

- [FDA draft guidance: AI to support regulatory decision-making (Jan 2025)](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/considerations-use-artificial-intelligence-support-regulatory-decision-making-drug-and-biological)
- [DLA Piper summary of the FDA AI draft guidance](https://www.dlapiper.com/en/insights/publications/2025/01/fda-releases-draft-guidance-on-use-of-ai)
- [FDA CDER: AI for drug development](https://www.fda.gov/about-fda/center-drug-evaluation-and-research-cder/artificial-intelligence-drug-development)
- [EMA and FDA align on Good AI Practice (Jones Day, Jan 2026)](https://www.jonesday.com/en/insights/2026/01/ema-and-fda-align-on-good-ai-practice-in-drug-development)
- [EU draft GMP Annex 22 on AI (PharmTech)](https://www.pharmtech.com/view/europe-tried-to-ban-generative-ai-from-critical-gmp-the-ban-may-not-survive-it-does-not-matter-)
- [FDA Computer Software Assurance final guidance (Federal Register, Sept 2025)](https://www.federalregister.gov/documents/2025/09/24/2025-18468/computer-software-assurance-for-production-and-quality-system-software-guidance-for-industry-and)

**Models and AI infrastructure**

- [Claude Opus 4.6 launch coverage (R&D World)](https://www.rdworldonline.com/claude-opus-4-6-targets-research-workflows-with-1m-token-context-window-improved-scientific-reasoning/)
- [Anthropic models overview](https://platform.claude.com/docs/en/models/overview)
- [Anthropic model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations)
- [Amazon Bedrock models under FedRAMP / GovCloud (AWS)](https://aws.amazon.com/compliance/services-in-scope/FedRAMP/amazon-bedrock-models/)
- [Claude in Amazon Bedrock approved for FedRAMP High (Anthropic, June 2025)](https://www.anthropic.com/news/claude-in-amazon-bedrock-fedramp-high)
- [DeepSeek V4 preview release](https://api-docs.deepseek.com/news/news260424/)
- [States that banned DeepSeek (StateTech)](https://statetechmagazine.com/article/2025/04/these-states-have-banned-deepseek)
- [MCP joins the Agentic AI Foundation](https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/)
- [LangChain and LangGraph 1.0](https://www.langchain.com/blog/langchain-langgraph-1dot0)
- [Pinecone BYOC docs](https://docs.pinecone.io/guides/production/bring-your-own-cloud)
- [Tetra Empower Agent (TetraScience)](https://developers.tetrascience.com/docs/waters-empower)
- [Migrating off AWS QLDB (Certyo)](https://www.certyos.com/en/blog/aws-qldb-migration-lesson)

**Market and competitors**

- [Tufts value of a day of delay (Contract Pharma)](https://www.contractpharma.com/updates-on-the-value-of-a-day-of-delay-in-drug-development/)
- [RIM system market (Grand View Research)](https://www.grandviewresearch.com/press-release/global-regulatory-information-management-rim-system-market)
- [Celegence automates CMC Module 3 (Manufacturing Chemist)](https://manufacturingchemist.com/celegence-pioneers-industry-first-automation-of-cmc-module)
- [AI CMC authoring software comparison 2026 (IntuitionLabs)](https://intuitionlabs.ai/articles/ai-cmc-authoring-software-comparison)
- [Veeva unveils Falcon and Agentic Authoring (Clinical Trial Vanguard)](https://www.clinicaltrialvanguard.com/conference-coverage/veeva-unveils-falcon-ai-platform-and-agentic-authoring-at-2026-summit/)

**GenAI and agentic technologies (section 28)**

- [GEPA: Reflective Prompt Evolution (arXiv, ICLR 2026)](https://arxiv.org/pdf/2507.19457)
- [DSPy GEPA optimizer docs](https://dspy.ai/current/api/optimizers/GEPA/overview/)
- [V-JEPA 2 (Meta, GitHub)](https://github.com/facebookresearch/vjepa2)
- [LLM-JEPA (arXiv)](https://arxiv.org/html/2509.14252v2)
- [AMI Labs and JEPA (TorontoStarts)](https://torontostarts.com/2026/09/16/ami-labs-world-models-jepa/)
- [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Claude citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Open-source OCR and document VLMs compared (Spheron)](https://www.spheron.network/blog/best-open-source-ocr-vlm-self-host-gpu-cloud-2026/)
- [ColPali (Hugging Face)](https://huggingface.co/blog/manu/colpali)
- [MCP 2025-11-25 spec update (WorkOS)](https://workos.com/blog/mcp-2025-11-25-spec-update)
- [MCP 2026-07-28 release candidate](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)
- [Advanced tool use (Anthropic Engineering)](https://anthropic.com/engineering/advanced-tool-use)
- [Agent Skills open standard (SiliconANGLE)](https://siliconangle.com/2025/12/18/anthropic-makes-agent-skills-open-standard/)
- [State of OpenTelemetry GenAI conventions, July 2026](https://john-hodge.com/blog/opentelemetry-genai-semantic-conventions/)
- [A2A protocol one year on (Linux Foundation)](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year)

**Whole-eCTD platform (sections 7–9, 21–26, 29, 33)**

- [Weave Bio and Takeda across 14 programs (HIT Consultant, Sept 2026)](https://hitconsultant.net/2026/09/01/weave-bio-takeda-collaboration-ai-regulatory-automation-ind-drug-development/)
- [Weave Bio launches NDA workflow with Parexel (Business Wire, April 2026)](https://www.businesswire.com/news/home/20260429322286/en/Weave-Bio-Launches-NDA-Workflow-Designed-in-Partnership-with-Parexel-Extending-AI-Native-Platform-Coverage-Across-the-Full-Regulatory-Lifecycle)
- [FDA binding guidance on standardized study data (CDISC)](https://www.cdisc.org/FDA-Final-Binding-Guidance-on-Standards)
- [FDA Study Data Technical Conformance Guide](https://www.fda.gov/media/88173/download)
- [eCTD v4.0 implementation timelines (IntuitionLabs)](https://intuitionlabs.ai/articles/ectd-v4-implementation-guide-timelines)
- [ICH M11 in force (Sakara Digital)](https://sakaradigital.com/blog/ich-m11-machine-readable-protocol-clinical-systems/)
- [ICH M4Q(R2) changes to Modules 2.3 and 3 (EUREG)](https://eureg.ie/ich-m4qr2-modules-2-3-and-3-2/)
- [R Consortium Pilot 1 submission package (GitHub)](https://github.com/RConsortium/submissions-pilot1-to-fda)
- [openFDA drug labeling API](https://open.fda.gov/apis/drug/label/)
- [FDA's 202 published CRLs, 74% citing quality/manufacturing (Pharma Manufacturing)](https://www.pharmamanufacturing.com/all-articles/article/55302937/fdas-crls-reveal-74-of-applications-rejected-for-quality-manufacturing-issues)

**Weave Bio product and design (section 34)**

- [Weave Bio home page](https://www.weave.bio/)
- [Weave Bio Submission Builder](https://www.weave.bio/platform/submission-builder/)
- [Weave Bio HAQ Manager](https://www.weave.bio/platform/haq-manager/)
- [Weave Bio security and privacy](https://www.weave.bio/security-and-privacy/)
- [About Weave Bio](https://www.weave.bio/about-weave-bio/)
- [AutoIND study by Weave and Takeda authors (arXiv 2509.09738)](https://arxiv.org/abs/2509.09738)
- [Regfo vs Weave Bio, written by Regfo's founder (BrightByte)](https://thebrightbyte.com/playbook/expertise/regfo-vs-weave-bio)
- [Weave Bio company profile (Excedr)](https://www.excedr.com/blog/weave-bio-ai-powered-regulatory-automation-for-drug-development)

**Real data, anchor drug and OCR stress test (sections 12 and 36)**

- [Big data collection in pharmaceutical manufacturing (Lek/Sandoz dataset, Scientific Data 2022)](https://www.nature.com/articles/s41597-022-01203-x) and its [Laboratory.csv on figshare](https://figshare.com/articles/dataset/Laboratory_csv/16676263)
- [Kerendia FDA chemistry review, NDA 215341 (Drugs@FDA)](https://www.accessdata.fda.gov/drugsatfda_docs/nda/2021/215341Orig1s000ChemR.pdf)
- [Kerendia US label, revised July 2025](https://www.accessdata.fda.gov/drugsatfda_docs/label/2025/215341s009lbl.pdf)
- [Health Canada Public Release of Clinical Information](https://clinical-information.canada.ca/)
- [EMA clinical data publication](https://www.ema.europa.eu/en/human-regulatory/marketing-authorisation/clinical-data-publication)
- [CDISC SDTM/ADaM pilot project (GitHub)](https://github.com/cdisc-org/sdtm-adam-pilot-project)
- [openFDA complete response letters](https://open.fda.gov/apis/transparency/completeresponseletters/)
- [DailyMed SPL resources](https://dailymed.nlm.nih.gov/dailymed/spl-resources.cfm)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract), [RapidOCR](https://github.com/RapidAI/RapidOCR) and [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)

**Independence audit (section 30)**

- [Beck et al. (2025), Bias in the Loop: How Humans Evaluate AI-Generated Suggestions (arXiv 2509.08514)](https://arxiv.org/abs/2509.08514v1)
- [Datanovia: AI as a QC double-programmer, quoting PHUSE guidance on independence](https://www.datanovia.com/learn/pharma-clinical/08-agentic-clinical-programming/ai-as-qc-double-programmer)
- [R Consortium Pilot 1: its ADaM data come from PHUSE's TDF\_ADaM\_v1.0 re-release of the CDISC pilot (GitHub README)](https://github.com/RConsortium/submissions-pilot1)
