# LEARN T-074 - Every limit from one spec fact; bad data goes to a person
Built: each result group now names the ONE specification fact its limit comes from; where there is none, the writer gives only the range. If a long-term or intermediate result is outside its limit, code writes "HUMAN REVIEW REQUIRED" and no shelf life is proposed.
The writer is a template filler: Gemma picks a sentence pattern and slot names, code writes every value. It was tested on 20 new tasks, 14 of them with bad data.
Why this way: we did NOT hide the wrong patterns from the model (T-073 did), because then it could never choose wrongly and the checks could never be seen working. We also did NOT call this "wording freedom": the patterns are in the prompt.
We did NOT link the real Degradation product or Assay to a spec fact just because a number matched: nothing public says which impurity it is.
New words: template filler = model picks a pattern, code fills values; human review route = marker written by code when data are bad.
Look at: ectd_engine/summary/m23_rules4.py - one limit per group, and "unknown limit" is never counted as zero outside.
Try it: python -m unittest tests.test_m23_v4_tasks tests.test_m23_v4_writer - it should say OK (35 tests, each check has a planted case that must fail).
Remember: a check that never fires on real model output is only proven by planted tests, so say so plainly.
