# LEARN T-013 - A number is trusted only when two independent originals agree
Built: agree() looks at all facts for one measurement and says Verified, SingleSource or Conflict. drift() compares a stored number with a fresh re-read of its source.
Why this way: We could have counted every matching fact. We did not: a copy of a number is not a second witness, so copies and unknown origins never count.
Counting different documents (doc_id), not different rows, stops one file from vouching for itself.
New words: lineage = whether a fact is an original, a copy, or unknown; route = one independent source document; drift = a source changed after we stored its number.
Look at: ectd_engine/gate/agree.py - routes is a set of doc_ids taken only from "original" facts.
Try it: python -m unittest tests.test_agree -v - 10 tests say ok, including 0.14 vs 0.014 -> conflict.
Remember: Two copies of one number are still one witness.
