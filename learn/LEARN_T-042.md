# LEARN T-042 - Does the checker hold up with a real model?
Built: a run of the real model (gemma4:e4b) on 130 real windows of Lek batches, plus an audit script that re-reads each finished section against the stored numbers.
Why this way: the fake model only proves the rules work on text we wrote; real text shows if wrong text slips through. Not chosen: loosening any word list to raise the pass rate, because that hides problems instead of measuring them.
New words: false reject = good text the checker refused; blind sheet = answers to judge without seeing the checker's verdict.
Look at: evidence/T-042/summary.md - accepted count, re-read wrong count, rules that fired on retried drafts.
Try it: python tools/audit_p54.py --run evidence/T-042/run/p54_ollama_gemma4-e4b --out evidence/T-042 - prints the summary, "wrong = 0".
Remember: your blind labels in blind.csv are the one check that does not use our own code.
