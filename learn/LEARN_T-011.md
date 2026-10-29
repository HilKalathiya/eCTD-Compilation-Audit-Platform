# LEARN T-011 - The gate that sorts good numbers from bad ones
Built: A gate that checks every new number (all fields, known batch, right unit, believable size). Good ones go into the fact store; bad ones go to a quarantine shelf with a reason.
Why this way: Rules live in plain tables (units.json, ranges.json) instead of code or a model, so a person can read and change them. We did NOT auto-fix bad rows: a fix would be a guess, so a person decides later.
New words: quarantine = a shelf for rejected rows, kept with a reason; false alarm = a good row wrongly rejected; rule table = a list of allowed units and sizes.
Look at: ectd_engine/gate/gate.py - submit() runs the checks in order and nothing is ever dropped.
Try it: python -m unittest tests.test_gate -v - you should see all gate tests OK, including the "honest gap" one.
Remember: a number that is wrong but looks believable (0.14 -> 0.014) passes this gate; only a second, independent reading (C1.4) can catch it.
