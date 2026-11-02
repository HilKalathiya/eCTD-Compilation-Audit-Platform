# LEARN T-040 - Same text, same verdict: old checker vs new checker
Built: a script that takes every paragraph Gemma really wrote (171) and asks both the old checker and the new copy to judge it, then compares the two answers.
Why this way: we replay real model text, not only hand-made test cases. Not chosen: trusting the 43 copied tests alone, because real text can hit odd cases the tests never thought of.
New words: replay = run saved inputs again through new code; verdict = accepted or rejected, plus the reasons.
Look at: tools/replay.py - `Judge.verdict` is the one place both checkers are run the same way.
Try it: python tools/replay.py - it should print "171 drafts, 171 same, 0 different".
Remember: a copy is only proven good when it judges real work exactly like the original.
