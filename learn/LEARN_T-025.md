# LEARN T-025 - One command shows the whole data spine working
Built: `demo_facts.py` loads three real public sources into two live databases and prints 5 proofs.
It exits 0 only if every proof holds, so a recruiter can run it and watch.
Why this way: every demo id starts with `DEMO25-`, so the demo can wipe and reload itself without touching other data.
We did NOT use a separate database schema: the limited login cannot create one, and a prefix is simpler.
Each proof re-reads the original file (CSV row, PDF box) instead of trusting what was stored.
New words: prefix = fixed start of a name | proof = a check that re-reads the source | quarantine = holding pen for rejected rows
Look at: ectd_engine/demo_facts.py - `prefixed()` renames ids on the way in without changing the loaders.
Try it: python -m ectd_engine.demo_facts - 5 lines starting PROOF n OK, then ALL 5 PROOFS HOLD (about 70 s).
Remember: a number is only trusted if you can walk back to its page, box or row.
