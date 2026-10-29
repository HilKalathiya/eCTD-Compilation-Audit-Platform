# Requirements and risks (T-006)

Every later task cites these ids (UR = user requirement, RK = risk). Source: `handoff/brain/01_design_on_one_page.md`.
In "Test or chunk": a path means a test that exists today; `future:<name>` means a later chunk will add it.

## Requirements

| ID | Requirement | From |
|---|---|---|
| UR-01 | The language model never writes a number; code renders every value from a fact ID. | The rule |
| UR-02 | Every fact carries a pointer to the source it came from. | Step 1 |
| UR-03 | A candidate fact is checked for unit and plausible range before it is accepted. | Step 2 |
| UR-04 | Copies never count as independent agreement; unknown lineage is treated as a copy. | Step 2 |
| UR-05 | When independent routes disagree, the fact goes to a human queue. | Step 2 |
| UR-06 | Nothing unchecked enters the fact store; failed rows are quarantined with a reason. | Step 3 |
| UR-07 | A computed result is stored as a new fact that records its inputs and the code version. | Step 4 |
| UR-08 | All rounding uses Decimal with ROUND_HALF_UP to the specified decimals, never float or round(). | The rule |
| UR-09 | Draft prose may contain only `[[placeholders]]` for values, and the validator rejects any stray number. | Step 5 |
| UR-10 | A value may appear only next to words that match its role, test, batch and time (no wrong binding). | Step 6 |
| UR-11 | Sentences with all/every/no/none/only are treated as claims and re-tested by code. | Step 6 |
| UR-12 | The finished text is re-read independently against the raw table. | Step 6 |
| UR-13 | A reviewer can click any number and see its source cell. | Step 7 |
| UR-14 | Human sign-off is blocked while any check has failed. | Step 7 |
| UR-15 | The ledger is hash-chained so any edit to a past entry is detectable. | Step 8 |
| UR-16 | Every action, model call, tool call and data pull is recorded in the ledger. | Step 8 |
| UR-17 | A changed source lists every affected placement and flags its prose for re-review. | Evidence graph |
| UR-18 | The same fact is identical everywhere it appears (modules, label, regions). | Evidence graph |
| UR-19 | Every new check ships with a planted-error test showing it can fail. | The rule |

## Risks

| ID | Risk | Sev | Control | Test or chunk | Covers |
|---|---|---|---|---|---|
| RK-01 | The model invents or alters a number in prose. | H | Placeholders only; validator rejects digits outside placeholders. | writer_test/tests | UR-01, UR-09 |
| RK-02 | A real fact is placed where it does not belong (wrong batch, month or test). | H | Closed vocabulary, role-bound placeholders, code-owned trend words. | writer_test/writer_test/mutation_test.py | UR-10, UR-11 |
| RK-03 | A fact has no traceable source. | H | Write gate refuses a fact without a source pointer. | future:write-gate | UR-02, UR-13 |
| RK-04 | Two copies of one value are counted as two independent confirmations. | H | Lineage check: copies and unknown lineage never count as independent. | future:independence-check | UR-04, UR-05 |
| RK-05 | Rounding drifts (float or Python round) and a reported value is off by one in the last digit. | H | Decimal ROUND_HALF_UP only; floats rejected in storage columns. | tests_live/test_databases.py | UR-08 |
| RK-06 | An implausible or wrong-unit value enters the fact store. | H | Unit and range check at the write gate; failures quarantined with a reason. | future:write-gate | UR-03, UR-06 |
| RK-07 | The audit trail is edited after the fact without anyone noticing. | H | SHA-256 hash chain; verification fails if any past entry changes. | future:ledger-chain | UR-15, UR-16 |
| RK-08 | A reviewer signs a section that still has a failed check. | H | Sign-off action is blocked while any check is red. | future:signoff-gate | UR-14 |
| RK-09 | A computed statistic cannot be reproduced later. | M | Result stored as a fact with inputs and code version. | future:compute-facts | UR-07 |
| RK-10 | A sentence like "all batches comply" is false but reads fine. | M | Absolute words become claims that code re-tests against the facts. | writer_test/tests | UR-11 |
| RK-11 | The model's text drifts from the source table after drafting. | M | Independent re-read of the finished text against the raw table. | writer_test/writer_test/mutation_test.py | UR-12 |
| RK-12 | A source changes but old prose and other modules keep the old value. | M | Evidence graph lists affected placements and flags prose for re-review. | future:consistency-engine | UR-17, UR-18 |
| RK-13 | A check is quietly weakened or deleted so a run passes. | H | Watch tool flags weakened tests; each check has a planted-error test. | tests/test_watch.py | UR-19 |
| RK-14 | A reviewer cannot see where a number came from. | M | Click-through from number to source cell in the review screen. | future:review-screen | UR-13 |
