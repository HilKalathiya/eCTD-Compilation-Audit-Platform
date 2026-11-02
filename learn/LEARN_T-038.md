# LEARN T-038 - Move the proven checker into the engine
Built: copied the paragraph checker (facts, validator, re-read check) from the frozen writer_test into ectd_engine, plus all 43 tests and the planted-error test.
Why this way: we copied, not rewrote, so the old proof still holds; the only real change is that every number is now a Decimal. Not chosen: rewriting the checker clean, which would throw away the 8303-of-8303 proof.
New words: port = copy code to a new home and make it fit; mutant = a deliberately wrong paragraph; kill rate = share of mutants the checker rejects.
Look at: ectd_engine/writer/facts.py - to_decimal / decimal_task / tolerance at the top.
Try it: python -m unittest tests.test_validator_port tests.test_mutation_port - "Ran 47 tests ... OK".
Remember: the port must catch as many wrong paragraphs as the original, and it does (8303 of 8303, same report line for line).

## Numbers: original (writer_test, run in place) vs port
- Tests: original 43 (`python -m unittest discover tests`, in writer_test/) -> port 43 in tests/test_validator_port.py (same names, same assertions); plus 4 wrapper tests for the mutation port.
- Planted errors caught: original 8303/8303; port 8303/8303. Correct text accepted: 1008/1008 both ways; hand-written wrong paragraphs caught 26/26 both ways. The port's printed report is identical to the original's (diff empty, apart from the timing line).

## Diff report (every changed line vs the original; line endings ignored)
ectd_engine/validator/validator.py: NO changes (byte-identical). It has no numbers, only text rules.
ectd_engine/validator/rendercheck.py:
- `from .facts import fmt` -> `from ectd_engine.writer.facts import fmt`: facts.py now lives in another package.
ectd_engine/writer/facts.py (rest is identical):
- ADDED `to_decimal(value)`: Decimal(str(value)); a float from JSON is read as its text, so 0.1 stays 0.1 (Decimal(0.1) would not).
- ADDED `decimal_task(task)`: copy of the task with batch values and spec lower/upper/limit as Decimal. Called first thing in compute_facts, so nothing downstream sees a float.
- ADDED `tolerance(decimals)` = Decimal("0.5") * Decimal(10) ** -decimals: replaces `0.5 * 10 ** (-dec)`, which is a float.
- pooled_slope: `xs += months` -> `xs += [Decimal(m) for m in months]`: int/int division gives a float; Decimal/int stays Decimal.
- pooled_slope: `else 0.0` -> `else Decimal(0)`: a float zero.
- trend_label: `max(0.05 * scale, 0.5 * 10 ** (-d))` -> `max(Decimal("0.05") * scale, tolerance(d))`: 0.05 and 0.5 were float literals; multiplying float by Decimal raises an error.
- compute_facts: first line `task = decimal_task(task)` (new).
- compute_facts, `thr = max(0.05 * (...), 0.5 * 10 ** (-dec))` -> `max(Decimal("0.05") * (...), tolerance(dec))`: same float-literal reason.
- Not changed on purpose: fmt() (already Decimal, ROUND_HALF_UP), `flags["slope_per_month"]` (now a Decimal instead of float; nothing reads it), no float()/round() anywhere in the port.
tests/test_validator_port.py (rest identical, all 43 test bodies unchanged):
- docstring (what the file is for); `import sys`.
- imports `writer_test.facts/validator` -> `ectd_engine.writer.facts` / `ectd_engine.validator.validator`.
- tasks.json is read from the frozen folder `writer_test/data/` (not copied: no duplicate data, frozen folder untouched).
- test_examples_in_prompt_pass_the_validator: prompt.py is not part of this card, so the test adds the frozen folder to sys.path just for the import and cleans up after, so the name "writer_test" cannot clash with other tests.
tests/test_mutation_port.py (rest identical, incl. generator, oracle, 25 mutations, 4 tampers, LEGIT, HAND_WRONG):
- docstring; imports point at the engine modules; ROOT -> writer_test/ (only data/tasks.json read).
- main(argv=None) so a test can call it; default report path is the temp folder, not writer_test/outputs (frozen folder is never written).
- open() of tasks.json wrapped in `with` (closes the file; the original left a ResourceWarning).
- `print("\n".join(L))` -> `print(chr(10).join(L))` (same output) and main() now returns its counts.
- ADDED class MutationPortTest (4 tests): no correct text rejected; every planted error caught; caught/total >= the original's 8303/8303; all 26 hand-written wrong paragraphs caught.
- The generator still uses float random numbers and round(): it only makes test data, it lives in tests/, and keeping it keeps the same random sequence, so the port sees exactly the same 1008 tasks as the original.
