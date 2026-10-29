# LEARN T-018 - two new ways to say where a number came from
Built: A fact can now point to an XML label (xml=/path) or to a hand-typed page (typed=page=N).
The made-up box 0,0,0,0 is gone; Python and Postgres accept and refuse exactly the same strings.
Why this way: A pointer must be true, so typed numbers say only "page N" instead of a fake box.
We did NOT loosen the old forms; we added two and a new migration file (004), leaving 001-003 untouched.
New words: locator = address of a fact's source; XPath = a path through XML tags like /doc/item
Look at: tests/test_fact_schema.py - LocatorFormsLive sends the same good/bad list to Python and to Postgres.
Try it: python -m unittest tests.test_fact_schema -v - see LocatorFormsLive run (not skipped) with Docker up.
Remember: One rule written twice (Python and database) must be tested against the same examples.
