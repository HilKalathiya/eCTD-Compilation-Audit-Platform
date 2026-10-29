# LEARN T-006 - Write down the promises and the dangers
Built: one page (docs/requirements.md) listing 19 promises the system makes (UR) and 14 things that could go wrong (RK).
A test reads the page and fails if the list is sloppy.
Why this way: we wrote promises first and tests later, so every test can say which promise it proves.
We did NOT put the list in a spreadsheet tool: plain text in git is versioned and a test can read it.
New words: requirement = a promise the system must keep; risk = something that could break a promise; GAMP 5 = pharma guide for validating software against written requirements; control = the thing that stops a risk.
Look at: docs/requirements.md - the last column of the risk table links each risk to the promises it protects.
Try it: python -m unittest tests.test_requirements -v - 7 tests, all ok (5 of them break the page on purpose and must fail).
Remember: if a promise has no risk and no test, nobody can prove the system keeps it.
