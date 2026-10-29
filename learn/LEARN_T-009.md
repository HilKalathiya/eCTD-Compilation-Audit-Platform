# LEARN T-009 - Facts in a database with only one door
Built: A Postgres table for facts. The app's login can read it and call one function to add a fact, nothing else.
Why this way: The database itself says "no" to direct writes (permission), so even buggy app code cannot sneak in a number.
We did NOT only check in Python, because a check in Python can be skipped; a database permission cannot.
New words: role = a database login with allowed actions; permission = one allowed action; SECURITY DEFINER = function runs with its owner's rights; append-only = add yes, change/delete no.
Look at: ectd_engine/db/migrations/001_facts.sql - REVOKE/GRANT lines at the bottom, and the gate function above them.
Try it: python -m unittest discover tests_live -v - the INSERT/UPDATE/DELETE tests print "permission denied for table facts".
Remember: One physical door beats a polite sign saying "please use the door".
