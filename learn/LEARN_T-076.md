# LEARN T-076 - One connected chain from the CSV, and a kit for a stranger to fool the checker
Built: the demo now starts from the real stability CSV and every number in the saved files is traced back to a CSV line. A second tool hands a stranger copies of the files and scores how many of their sneaky edits the checks find.
Why this way: we did NOT keep the invented test task as the default, because a demo on invented numbers cannot show that real data flows through. We also did NOT count the scripted "classmate" as the real test: code only tries what we already thought of; a person will not.
New words: run fingerprint = a short code made from the hashes of the saved files, so one run can be found again (it is not a tamper-proof log); classmate test = a person who is not on the team edits copies and we see which edits the checks find.
Look at: tools/classmate_kit.py - run_checks (step 1) never opens answers.csv; match_answers (step 2) does, afterwards.
Try it: python tools/demo_checkpoint_a.py --out evidence/T-076/demo/try1 --mock - the SOURCE TRACE line should say all numbers trace to the CSV.
Remember: a check that says "something changed" is weaker than one that says "here".
