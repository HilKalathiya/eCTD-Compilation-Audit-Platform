# LEARN T-001 - Take a snapshot, then add an empty engine skeleton
Built: A git snapshot of all existing work, then an empty ectd_engine/ folder with four named parts and one smoke test.
Why this way: We committed the old work untouched first so "before" and "after" can be compared. We did NOT mix both
in one commit, because then the watch tool could not tell old files from new ones.
New words: git = a tool that saves numbered snapshots of a folder; commit = one saved snapshot;
baseline = the snapshot you compare future changes against; .gitignore = a list of files git must skip.
Look at: tests/test_smoke.py - it just imports every part; if a part breaks, this fails first.
Try it: python -m unittest discover tests - you should see "Ran 1 test ... OK".
Remember: Snapshot first, change second, so every change can be seen.
