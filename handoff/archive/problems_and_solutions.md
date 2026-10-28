# eCTD Platform — Problems and Solutions

Oct 24, 2026 · @hil Kalathiya

## Numbers, data and evidence

| Problem | Solution |
| --- | --- |
| The model types data values into scripts and writes provenance itself, so one typo or invented page goes unnoticed | Tools accept fact IDs only, never raw numbers. Provenance is read-only, joined from the fact record at render time. A seeded-typo test must be blocked |
| Milestone 1 is judged by "retrieval in under 500 ms", but speed is not the risk | Every record of a reference study is retrieved: counts and checksums match a manual export, with nothing missing or duplicated. Speed is measured, never the gate |
| The VLM reads peak areas off chromatogram charts | Take integrated results from an Empower Export Method ([Waters](https://support.waters.com/KB_Inf/Empower_Tips_of_the_Week/WKB193142_Exporting_Data_Results_and_Reports_with_Export_Methods_in_Empower)) or the printed results table in CMO PDFs. The VLM only counts peaks as a sanity check |
| ">99.5% extraction accuracy" is undefined and still allows an error in every large document | Seed known errors into a held-out set. Report how many were flagged (target: all) and how many correct values were flagged by mistake. State the context of use ([FDA draft, January 2025](https://www.fda.gov/media/184830/download)) |
| "Graph RAG" can mean an LLM inventing links between GMP facts | Deterministic code builds every edge from source keys and writes it through the write gate. LLM-proposed edges go to a review queue only |
| "PyChain WASM" does not exist | A validated statistics library, called as tools with fact IDs. Free code runs only in a Firecracker microVM (no network, thrown away after each run) and is labelled non-GMP |
| The example script types values in, has a nearly blind OOT test, averages a trend and rounds wrongly | Load values by fact ID. Test OOT with a 95% prediction interval from earlier time points. Report the slope or a per-time-point mean. Round with `Decimal` and `ROUND_HALF_UP` to the specification's decimals |
| "100% mathematical accuracy" covers arithmetic only, not wrong inputs, methods or rounding | Validate against NIST's certified [Statistical Reference Datasets](https://www.itl.nist.gov/div898/strd/) and against JMP or SAS on edge cases. The test suite is the validation evidence |

## Infrastructure, models and security

| Problem | Solution |
| --- | --- |
| Pinecone Serverless, Neo4j Aura and OpenAI embeddings send data outside the promised isolated boundary | Neo4j Enterprise in the customer's VPC (Aura only with PrivateLink, a [preview](https://neo4j.com/docs/aura/security/private-endpoints/) in Ireland, London and Paris). pgvector in the Postgres backup. [Titan Text Embeddings V2](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-titan-text-embeddings-v2.html) in the same region, or an open model on own GPUs |
| "LangGraph v0.3+" is outdated | Target 1.2.x (1.2.16 shipped 16 October 2026, [release list](https://releases.sh/langchain/langgraph-releases.md)). Pin it in the lockfile. Adopt the 1.1 "v2" output format in one planned change |
| Claude Opus 4.6 inside GovCloud would call an API outside the boundary | Bedrock in the customer's commercial region, with a model [AWS lists there](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html), such as Haiku 5.5 or Sonnet 5.5 in Frankfurt, Ireland, Paris or Stockholm. Anthropic's API has [no EU-only option](https://platform.claude.com/docs/en/manage-claude/data-residency). Pin the version |
| A 1M-token context cannot hold 50,000 pages, and cost grows with tokens | Retrieval first. Read one report or one evidence pack per call, under a token budget. Cache repeated evidence and log tokens per call |
| Silent fallback to another model changes outputs in a validated system | Pause and queue when the model is down. Switch only to a model validated for that task beforehand, and log the switch with every output. Keep LLM output behind code checks and sign-off, as the [draft Annex 22](https://health.ec.europa.eu/consultations/stakeholders-consultation-eudralex-volume-4-good-manufacturing-practice-guidelines-chapter-4-annex_en) expects |
| GovCloud is the default deployment | One commercial AWS region per customer: Frankfurt or Ireland for EU, a US region for US. GovCloud only for government-funded programs |
| The infrastructure is called "FedRAMP High, HIPAA, Part 11 compliant" | Say "supports the customer's Part 11 compliance". The customer validates, as [AWS states](https://docs.aws.amazon.com/zh_cn/whitepapers/latest/gxp-systems-on-aws/appendix-21-cfr-11-controls-shared-responsibility-for-use-with-aws-services.html). Ship a validation package and a matrix of who owns each control |
| Nitro Enclaves are proposed for GPU inference | One AWS account and VPC per customer, private endpoints and customer-managed KMS keys. [Enclaves](https://docs.aws.amazon.com/enclaves/latest/user/nitro-enclave.html) only for key work, such as the ledger's signing key |
| "Memory enclave isolation across tenants" contradicts single-tenant | v1 is single-tenant. If multi-tenant later: a tenant ID on every row, [PostgreSQL row-level security](https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/rls.html) with `FORCE`, per-tenant keys, separate vector indexes, no shared prompt caches |

## Regulatory content and business

| Problem | Solution |
| --- | --- |
| Traceability is credited to 21 CFR Part 11 alone | Cite Part 11, 21 CFR 211.68 and 211.194, and FDA's 2018 [data integrity Q&A](https://www.fda.gov/media/119267/download). Build unique logins, an audit trail nobody can edit, second-person sign-off and a risk-based audit-trail review |
| HIPAA is framed as the CMC privacy rule | Tag trade secrets and confidential commercial information, which [21 CFR 20.61](https://www.law.cornell.edu/cfr/text/21/20.61) protects from disclosure. Mask staff names and signatures outside the GMP record (GDPR covers EU staff). Follow each CMO contract's access rules |
| The sample sentence puts Month 36 under accelerated storage, compares a total with an individual threshold, fixes the threshold at 0.20% and applies Q3B to a biologic | Render the sentence from typed facts. Code checks condition against time point, individual against total, the Q3B threshold from the maximum daily dose, and the drug type. Keep the rules in a versioned table: the revised ICH Q1 is [due for Step 4 in November 2026](https://database.ich.org/sites/default/files/ICH52_Q1_EWG_WorkPlan_2026_0318.pdf) |
| Specification limits are taken from other products' filings | Justify each acceptance criterion from this product's own data, as [ICH Q6A](https://database.ich.org/sites/default/files/Q6A%20Guideline.pdf) asks. Other products' limits appear only as labelled context |
| A stability trend is filed under 3.2.P.5.5 instead of 3.2.P.8.3 | Route by rule: trends to 3.2.P.8.3, impurity identity and origin to 3.2.P.5.5, reasons for acceptance criteria to 3.2.P.5.6. Keep the mapping versioned, since [ICH M4Q(R2)](https://database.ich.org/sites/default/files/ICH53_M4QR2_EWG_WorkPlan_2026_0818.pdf) plans Step 4 for June 2027 |
| The $8.4 billion market size has no source | Build it bottom-up: companies × CMC submissions per year × price per submission, with counts from FDA's [PDUFA dashboards](https://www.fda.gov/about-fda/fda-track-agency-wide-program-performance/fda-track-prescription-drug-user-fee-act-pdufa-performance-dashboards). Cross-check against the $5.11 billion RIM software forecast |
