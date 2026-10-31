# LEARN T-028 - Search the guidelines two ways and mix the answers
Built: A search that takes a question and returns the 5 best guideline passages, each with document, page and table id.
It looks up exact words AND similar meaning, then mixes the two lists.
Why this way: Word search misses rephrased questions; meaning search can miss exact terms. We did NOT choose one alone,
but the test shows vector-only (0.867) beat the mix (0.800) here, so the mixing rule may need work (T-029 adds a reranker).
New words: BM25 = word search that ranks by how rare and how often the words appear (Postgres ts_rank_cd is the close cousin); embedding = a list of 768 numbers that captures a text's meaning; RRF = mix lists by giving each hit 1/(60+rank) points and adding them up.
Look at: ectd_engine/knowledge/search.py - fuse() is the whole mixing rule in 6 lines.
Try it: python -m unittest tests.test_retrieval -v - prints HIT/MISS per question and the three recall numbers.
Remember: A guideline passage is a quote, never a fact: it has no value field and the gate refuses a kb= source.
