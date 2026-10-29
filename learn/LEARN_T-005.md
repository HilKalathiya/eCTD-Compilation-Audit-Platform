# LEARN T-005 - Two local databases that keep numbers exact
Built: One command starts Postgres (facts) and Neo4j (evidence graph) on this PC. Tests prove 0.140
stays 0.140, and alarms ring if a database column or graph property could turn it into 0.14.
Why this way: We keep Decimals as NUMERIC in Postgres and as text in Neo4j. The alternative, plain
float columns, is smaller but silently changes numbers. Profiles let us start only the DB we need.
New words: Docker = tool that runs programs in sealed boxes; container = one running box;
           volume = disk space that survives when the box is removed; profile = a named group of boxes
Look at: ectd_engine/db/graph.py - check_props refuses float values
Try it: python -m unittest discover tests_live - should print OK (7 tests, containers must be up)
Remember: Store numbers as exact text or NUMERIC, never as float.
