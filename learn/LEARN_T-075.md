# LEARN T-075 - Checkpoint A: one command shows the whole chain
Built: `python tools/demo_checkpoint_a.py` runs facts -> stats -> Gemma draft -> gates -> HTML + Word -> two planted errors, in 7 numbered steps.
It exits 0 only if the good path passes AND both planted errors are rejected.
Why this way: we did NOT make a separate fake "demo mode" with canned output; the demo calls the same writer, gates and cross-check as the real runs (only the data are labelled DEMO). We also did NOT let the demo pass if a plant slips through: that is what the sabotage test proves.
New words: checkpoint = planned stop where the whole chain is shown; sabotage test = a test that breaks the guard on purpose to see the alarm still rings.
Look at: tests/test_demo_checkpoint_a.py - the SabotageTest class swaps in "plants" that change nothing and expects the demo to fail.
Try it: python tools/demo_checkpoint_a.py --out evidence/T-075/demo/try1 --mock - the last line should say DEMO PASSED (exit 0).
Remember: a demo that cannot fail proves nothing.
