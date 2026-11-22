# LEARN T-064 - Gemma writes the stability paragraph, also as an Agent Skill
Built: A writer where the model writes sentences with [[slots]] and code fills in every number. The same writer also runs as an Agent Skill.
Why this way: Retry sends the rejected draft and its problems back, because at temperature 0 the same prompt would give the same wrong draft. We did NOT let the model type numbers (it can slip), and the skill does NOT copy the code: it calls the same entry point, so results match.
New words: Agent Skill = folder with SKILL.md that says when/how to run a job; entry point = the one function all routes use; retry feedback = send the bad draft + problems back; re-read = recount numbers from the data.
Look at: ectd_engine/stability/loop.py - draft_problems checks digits, unknown slots, missing slots, then the validator.
Try it: python tools/writer_run.py --kind p83 --backend mock --out outputs/p83_try - you should see 10/10 accepted, 0 wrong accepted.
Remember: The model writes the words, code writes the numbers, and a separate recount checks the result.
