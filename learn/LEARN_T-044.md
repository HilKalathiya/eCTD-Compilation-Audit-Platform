# LEARN T-044 - Stop waiting forever for a stopped database
Built: Connecting to Postgres or Neo4j now gives up after 5 seconds and says which one is down and how to start it.
A new test makes a closed port and a silent port and checks the error comes in under 15 seconds.
Why this way: The test suite hung ~260 s per file because Docker was stopped and nothing ever timed out.
We did NOT just raise the test time limit: that hides the problem and a check that hangs cannot fail.
New words: timeout = how long we wait before giving up; closed port = nothing listens there, the answer is instant "no"; silent port = something accepts but never replies (the old hang).
Look at: ectd_engine/facts/store.py - `connect_app` turns a connection error into `DatabaseDown` with the start command.
Try it: python -m unittest -v tests.test_db_down - 4 tests pass in about 17 s total.
Remember: A wait with no limit is a hidden failure; always give connections a timeout.
