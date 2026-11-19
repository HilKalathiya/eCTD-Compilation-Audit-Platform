# LEARN T-048 - Make the paragraph say how many results were outside the limit
Built: The prompt now asks for exactly 3 sentences with a fixed shape. The checker now rejects any paragraph that never says how many results were outside the limit.
Why this way: We fixed the prompt and made the check stricter. The alternative, letting the model skip sentence 3, gave 0 of 130 last time. Loosening the check would hide the problem.
New words: synthetic window = a test case made up on purpose (here: a moved limit) so some results fall outside; replay = run old drafts through the new checker.
Look at: ectd_engine/validator/spec.py - outside_statement_problems is the one new rule.
Try it: python -m unittest tests.test_spec_writer - you should see OK.
Remember: A stricter checker plus a clearer prompt works; a looser checker only hides mistakes.
