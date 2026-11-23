# LEARN T-071 - Gemma writes the words of Module 2.3, code writes every number
Built: Gemma now writes the text of the 2.3 summary using only named holes like [[shelf]]; code fills the holes from the stored facts.
Five gates check each draft; the independent cross-check of the saved HTML and Word file has the last word.
Why this way: we did NOT show Gemma any value or even a digit; it cannot copy a number it never sees.
We did NOT use a list of banned words ("overclaim" words); a closed list of allowed sentence forms and allowed words is safer, because a new bad word cannot slip past.
New words: slot = a named hole in the text that code fills; held-out = test cases never used while tuning; wrong-but-accepted = passed every gate but a number is wrong.
Look at: ectd_engine/summary/m23_loop.py gate_unit - gates a, b, c, e in one place; gate d is the cross-check call below it.
Try it: python -m unittest tests.test_m23_writer - it should say OK (a clean control passes; each planted bad draft is rejected by its own gate).
Remember: the model picks the words, the code picks the numbers, and a second program checks both.
