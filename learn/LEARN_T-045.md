# LEARN T-045 - Every database connect now gives up after 5 seconds
Built: The two connect helpers used by most tests and the demo now stop waiting after 5 s.
They raise the same clear "database is down, start it with..." error as the newer helpers.
Why this way: We reused the timeout number and error class from facts/store.py instead of copying them, so there is one place to change.
We did NOT wrap each test in a global timer, because that hides which connect was slow.
New words: DatabaseDown = our error meaning "the database did not answer in time"
Look at: ectd_engine/db/postgres.py - connect_timeout and the try/except around the connect.
Try it: python -m unittest tests.test_db_down - 8 tests pass in about 35 s total.
Remember: A connect without a timeout can wait forever; always set one.
