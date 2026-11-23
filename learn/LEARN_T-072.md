# LEARN T-072 - Make the 2.3 writing test honest
Built: the task files now hold only names and fact ids; every number is read from the graph when the document is built.
Gemma gets no answer text now; it picks its own wording from a closed list of 2-4 allowed wordings, and a new check ties "no result outside the limit" to the stored count.
Why this way: we did NOT put the answer back in the prompt to raise the score; a lower honest score is better than a high copied one.
We also did NOT reuse the old test tasks, because several contradicted themselves (a shelf life longer than the study that supports it).
New words: copy rate = share of answers copied from the prompt; cross-fact gate = a sentence must agree with a stored fact; graph source = numbers come from the database.
Look at: ectd_engine/summary/m23_tasks2.py consistency_problems - six rules every test task must pass, each with a refusing test.
Try it: python -m unittest tests.test_m23_v2_writer - it should say OK (control passes in every wording; each planted bad draft is rejected by its gate).
Remember: a test is only honest if the model cannot see the answer and the facts cannot contradict each other.
