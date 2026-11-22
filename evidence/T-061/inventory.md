# T-061 inventory: public stability content for 3.2.P.8.3

Status: STOPPED at step 2 (no code written). One source could not be opened by me, see row 1.

There is no `knowledge/` folder. The index code is `ectd_engine/knowledge/`. The public files are in `data/public/`.

| # | File | Page | What it holds | Public? | Checked how |
|---|---|---|---|---|---|
| 1 | `data/public/kerendia/215341Orig1s000ChemR.pdf` (FDA Chemistry Review, NDA 215341, 36 pp) | not found | Unknown. This is the one product-specific document, and a chemistry review often has a stability summary. | yes (FDA) | NOT CHECKED. My PDF scan was blocked by the auto-mode classifier, and Read on `data/public/` is denied by the permission settings. Decision D14 in `handoff/brain/02_decisions_log.md` says "no public real stability time series exists", but I have not confirmed it against this PDF. |
| 2 | `Laboratory.csv` (Lek/Sandoz, CC BY 4.0) | n/a | 55 columns: batch, materials, tablet physical tests, `dissolution_av`/`dissolution_min`, impurities. No stability, storage, condition or time-point columns. | yes | header read: no column matches stab/month/stor/cond/time. Matches `handoff/brain/03_evidence_and_results.md` line 27 ("no stability"). |
| 3 | `data/public/kerendia/kerendia_spl_v1.xml`, `kerendia_spl_v12.xml` (DailyMed labels) | n/a | Label text. Storage statement only, no result tables. | yes | `grep -c stability` = 0 in both files. |
| 4 | `data/public/ich/Q1A_R2.pdf`, `Q1E.pdf`, `M4Q_R1.pdf` | n/a | Guideline text: conditions (e.g. 25 C/60% RH, 40 C/75% RH), evaluation rules. Rules and quotable text, not results. | yes | Described in `data/public/SOURCES.md` ("used only as quotable text chunks, never as facts"). |
| 5 | `writer_test/data/tasks.json` | n/a | 8 SYNTHETIC stability tasks used by the frozen writer harness. | synthetic | Per `handoff/brain/03_evidence_and_results.md` section A. Not public real data. |
| 6 | `data/specs/lek_spec.csv`, `data/rules/*`, `data/tasks/*` | n/a | Spec limits, Q3B rules, P.5.4/P.5.6 task lists. | n/a | No stability content found by name. Not opened in detail. |

Result: nothing I could verify holds public stability RESULTS (conditions x time points x attributes) for our product.
The only source that might is row 1, and I could not read it.
