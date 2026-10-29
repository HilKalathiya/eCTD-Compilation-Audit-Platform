# LEARN T-014 - Two copies of every fact, and a checker that spots differences
Built: When the gate accepts a fact it now also writes it into the Neo4j graph (a map of facts, batches and sources).
A compare function lists any fact that is missing or different between Postgres and the graph.
Why this way: The gate is the only door, so both stores are filled from one place. We did NOT let the graph
read from Postgres later (a nightly copy), because then nobody would notice a hand-edit made in between.
Numbers are kept as text ("0.140") so no float can quietly change them.
New words: graph = data stored as dots (nodes) joined by lines; Cypher = Neo4j's query language; MERGE = create if missing, else reuse
Look at: ectd_engine/graph/compare.py - the check compares text, so "0.140" and "0.14" count as different.
Try it: python -m unittest tests.test_graph -v - 11 tests OK, the live one edits a graph node and the check catches it.
Remember: One door in, two stores out, and a checker that notices when they stop agreeing.
