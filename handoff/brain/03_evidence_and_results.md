# 03 Evidence and results (what is TESTED vs only DESIGNED)

## A. Writer harness (`writer_test/`, synthetic stability data, Gemma 4 E4B via Ollama) — TESTED
- Task: 8 synthetic 3.2.P.8.3 stability discussion paragraphs. Code computes numbers, trend, compliance; model writes 2–5 sentences with `[[placeholders]]`; validator + re-read check.
- Speed: laptop ~9–11 s/section once thinking was off (Gemma 4 is a thinking model: empty content when tokens go to thinking; fix `--think off`, `--num-predict 600`). Kaggle Gemma 4 26B ~3 s/section, 7/8 passed (older code).
- Blind comparison vs Claude on 5 sections (Hil rated): Gemma writing 4.0 / judgement 3.8 vs Claude 3.6 / 4.2 -> about even. Easy templated task; harder Module 2 test not done.
- Planted-error (mutation) test: 26 draft-error kinds + 4 tamper kinds, ~8,200+ errors per run all caught; 0 false rejections on 1,008 correct paragraphs; 10 legit paraphrases pass. Limit: author planted these errors (friendly test).
- Audit of the model's OWN accepted paragraphs (hand-labelled by Claude, Hil is not an auditor):
  - Round 1: 102/160 accepted -> 61 ok, 30 awkward, 7 misleading, 4 WRONG. Failed pass mark. 7 new checks added.
  - Round 2: 116/160 accepted -> 92 ok, 20 awkward, 4 misleading, 0 wrong. Pass mark met (>=100 accepted, none wrong). The 4 misleading exposed 3 more gaps, since closed (0/92 ok drafts rejected by the new checks).
  - Round 3 (fresh test, since fixes were made after seeing round-2 drafts): NOT RUN YET. Command: `python -m writer_test.run --model gemma4:e4b --audit 20` (close Excel first).
- Honest limits: only stability sections and one model; spec and clinical-narrative sections need their own word lists; magnitude words ("slightly") unchecked; test names mid-sentence not caught; wrong values in the fact store and true-but-unhelpful choices not covered; stricter checks lower the acceptance rate; real use needs a qualified human reviewer.
- Rule of three: 0 misses in n=300 still allows up to 1.0% (95% upper bound 1-0.05^(1/n)); n=116 -> ~2.5%.

## B. Checks stress test (`checks_stress_test/`, real data) — TESTED
- Test 1 (Lek batches, 4,000 picks of 2,894 facts): old value-only validator passes 100% of wrong-batch/wrong-test bindings, 50.4%/86.4% of last-digit slips (section/product level), 3.9/8.8% of decimal moves, 3.5/24.1% of digit swaps. Measures the OLD check, not the fix.
- Test 2 (CDISC pilot CSR, 35 narrative pages): ~1,100 digit strings; 6 results only in words, 4 words+digits, 5 distinct "none/no" statements -> number words and quantifiers must be handled.
- Test 3: CDISC ADSL vs R Consortium ADSL identical (copies). SDTM re-derivation matches CSR exactly (86/84/84 randomized; wk-24 completers 118; 3 deaths; 111 M/143 F). Planted flag errors: subject-level SDTM comparison caught 762/762 flips and 520/520 swaps; per-arm counts caught 0 of the swaps. Trap: SDTM WHITE 230 vs CSR "218 Caucasian; 12 Hispanic".

## C. OCR + VLM cross-check (`ocr_stress_test/`, simulation on real Lek values) — TESTED (simulated scans)
- 9,600 values at 4 scan qualities, Tesseract 5.3 + PP-OCR (RapidOCR). Naive (VLM sees OCR text): 84/170 wrong stored on poor/fax. Naive independent: 11.5%/22.8% sent to people. Fixed design: 0 wrong among 9,406 auto-accepted; 6.0% poor / 2.1% fax to people. Not yet tried on real CoA scans.

## D. Research facts (verified Oct 2026, sources in archive/explainer_full.md §38)
- 74% of 202 published CRLs (2020–2024) cited quality/manufacturing; delay cost ~ $0.8M/day (Tufts 2024).
- FDA Jan 2025 draft AI guidance excludes drafting aids; EU draft GMP Annex 22 bars GenAI in critical GMP use; FDA-EMA Good AI Practice principles Jan 2026.
- eCTD v4.0: FDA voluntary since Sep 2024; EMA optional from Dec 2025. ICH M11 Step 4 Nov 2025; M4Q(R2) Step 4 target Jun 2027.
- Lek dataset: semicolon CSV, column typo `resodual_solvent`; no assay, no spec limits, no stability; "impurity <= total" fails on 20 batches (quarantine them).
- Kerendia: FDA chemistry review covers 10/20 mg, 36-month expiry; July 2025 label adds 40 mg -> version-difference demo.
- No public real stability time series -> shelf-life code validated against R/NIST StRD + synthetic series.
