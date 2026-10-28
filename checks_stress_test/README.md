# Checks that cannot fail: three tests on real data

These are the tests behind section 30 of the explainer ("The same flaw elsewhere: checks that cannot fail").
They follow the OCR + VLM stress test in `ocr_stress_test`.

The rule being tested is that **a check counts only if it can fail**. That means:
- it has its own input;
- it tests meaning as well as value;
- it is graded by tests its builders did not write.

Nothing in the source files is altered. CDISC's terms forbid changing their data, so planted errors go only into in-memory copies and are never saved.

## Data (all public)

| File | Source | Used by |
|---|---|---|
| `Laboratory.csv` | Lek Pharmaceuticals (Sandoz) production data, Scientific Data 2022, figshare, CC BY 4.0 | `tracing.py` |
| `csr.pdf` | CDISC SDTM/ADaM Pilot Project study report (CDISCPILOT01), github.com/cdisc-org/sdtm-adam-pilot-project | `s2_number_words.py` |
| `sdtm_dm.xpt`, `sdtm_ds.xpt`, `sdtm_sv.xpt`, `cdisc_adsl.xpt` | Same CDISC pilot project (the SDTM and ADaM folders of the updated submission package) | `s3_rederive.py` |
| `rc_adsl.xpt` | R Consortium Pilot 1 submission to FDA, github.com/RConsortium/submissions-pilot1-to-fda (its ADaM data come from PHUSE's TDF_ADaM_v1.0 re-release of the CDISC pilot) | `s3_rederive.py` |

## Run

```
pip install pandas numpy pymupdf
python tracing.py Laboratory.csv          # -> tracing_results.json
python s2_number_words.py csr.pdf          # -> s2_results.json
python s3_rederive.py data/                # folder with the five .xpt files -> s3_results.json
```

Each script takes a few seconds.

## Results

**Test 1: `tracing.py`, the old number validator ("every digit traces to a fact").**

Method:
- Facts are built from 1,005 real batches.
- 400 simulated sections of 10 batches each are drawn. Ten facts per section are changed five ways, giving 4,000 picks of 2,894 distinct facts.
- For each changed value, the test asks the old question: does the same number (compared as a number) still exist in the section, or anywhere in the product?

| Error | Changed values | Still pass (section) | Still pass (product) |
|---|---|---|---|
| Wrong batch, right test | 3,128 | 100% | 100% |
| Wrong test, right batch | 3,595 | 100% | 100% |
| Last digit off by one | 4,000 | 50.4% | 86.4% |
| Decimal point moved one place (0.14 to 1.4 or 0.014) | 4,000 | 3.9% | 8.8% |
| Two digits swapped | 2,710 | 3.5% | 24.1% |

The first two rows are 100% by definition, and that is the point: a value-only check cannot see a wrong binding.

This test measures the old check, not the fix. Bound placeholders remove typed-number errors by construction. Wrong bindings are a different matter: they are caught only if the batch and test named in the sentence come from the same fact or are checked against it, and that check still has to be tested with planted errors.

**Test 2: `s2_number_words.py`, results a digit-only validator never sees.**

The test reads the 35 narrative pages of the 492-page CDISC pilot report (synopsis pp. 2-6, body pp. 12-41). It finds about 1,100 digit strings: results, but also table and section numbers and dates. A digit-only validator would also miss the following:

| What | Distinct | Counting synopsis repeats | Example |
|---|---|---|---|
| Results written only in words | 6 | 7 | "three laboratory analytes", "Nineteen of the 30 analytes" |
| Results written as words plus digits | 4 | 4 | "Eighty-six (86)" |
| "None"/"no" statements with no number | 5 | 8 | "None of the deaths were judged related to treatment" |

**Test 3: `s3_rederive.py`, independent routes.**

Two copies, not two routes:
- CDISC's ADSL was compared with the R Consortium's ADSL: 254 subjects, 45 shared variables, 0 different values.
- They are copies. The R Consortium took its ADaM data from PHUSE's re-release of the CDISC pilot.
- Their agreement shows the copy is faithful, not that the values are right.

Re-deriving from SDTM reproduces the report exactly:
- 86/84/84 randomized;
- 118 completing Week 24 (60/28/30);
- 110 completing the study (58/25/27);
- 3 deaths (2/1/0);
- 111 men and 143 women;
- mean age 75.1 (SD 8.25).

Subject by subject, the SDTM sets equal the ADaM flags COMP24FL, DCDECOD = COMPLETED and DTHFL.

Planted errors (in an in-memory copy only):

| Planted error | Planted | Caught by per-arm counts | Caught subject by subject |
|---|---|---|---|
| One flag flipped | 762 | 762 | 762 |
| Two flags swapped within an arm | 520 | 0 | 520 |

Re-counting the ADaM flags themselves would catch none of these, by definition.

Definition trap: SDTM has 230 WHITE subjects (218 not Hispanic, 12 Hispanic). The report says "218 (86%) Caucasian; ... 12 (5%) Hispanic", because its case report form used "Origin" categories. Matching the two by name gives a false conflict.

## Limits

- Test 1 measures the old check, not the fix.
- Test 3 shows the SDTM route reproducing the report and catching planted flag errors. Two caveats:
  - SDTM is also built by the sponsor, so a collection or mapping error would be shared by both routes.
  - The Week 24 completers used SV visit 12 alone. That matched only because all 118 patients are also in the efficacy population (EFFFL = Y), which the report's definition requires.
- Only one part of the validator fix holds by construction: the model never types a digit.
- The following fixes have not been measured yet:
  - binding checks;
  - number words and quantifier words;
  - lineage rules (unknown lineage must count as a copy);
  - consistency on exported files;
  - claim extraction by a model from a different family;
  - limits from a rule table;
  - blind reviewer confirmation;
  - held-out checks for GEPA;
  - outside-sourced seeded errors;
  - manifest completeness.

  They belong in the seeded-error study, with part of the errors written by people outside the team.
