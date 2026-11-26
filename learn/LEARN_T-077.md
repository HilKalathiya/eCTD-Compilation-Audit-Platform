# LEARN T-077 - Small fixes so the Checkpoint A doc says only what is true
Built: the demo takes the Dissolution unit from the CSV, labels the study sentence as DEMO, and has a one-line check for a single edited Word file. Two new tests change the CSV limit (NLT 75) and plant a number that cannot be traced.
Why this way: we did NOT hide the weak spots in the doc. 26 of the 33 numbers in each file come from invented DEMO rows (only 7 are public), and the spec table rows could not be labelled row by row because the frozen cross-check rejects a label inside a row (a test shows it); that needs an engine card.
New words: --check-docx = one command that checks one Word file and lists the numbers it rejects; template row = the Lek spec row used only for its field layout, every value then comes from the CSV.
Look at: tools/demo_checkpoint_a.py - label_demo and check_docx.
Try it: python tools/demo_checkpoint_a.py --check-docx evidence/T-076/classmate/kit1/for_classmate/M23.docx --kit evidence/T-076/classmate/kit1 - "rejected: 0".
Remember: a test that can fail is worth more than a sentence that sounds right.
