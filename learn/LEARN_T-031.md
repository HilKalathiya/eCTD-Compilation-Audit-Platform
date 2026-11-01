# LEARN T-031 - Re-reading search hits with a reranker
Built: After search finds 24 possible passages, a second model reads the question and each passage together and picks the best 5.
Result on the 30 gold questions: rerank 0.933, meaning-only 0.867, mixed 0.800, word-only 0.667.
Why this way: A cross-encoder [a model that reads question + passage as one text] judges the pair directly, so it is more accurate than comparing two separate number-lists. The price is speed: about 8 s per question on CPU, versus about 2 s for plain search. We did NOT rerank all 505 passages (far too slow) and did NOT add another vector model (it would not read the pair together).
New words: cross-encoder = model that reads question and passage together; reranker = step that re-orders search hits; float32 = normal-size numbers (float16 is much slower on CPU).
Look at: ectd_engine/knowledge/rerank.py - the whole model step is about 15 lines.
Try it: python -m unittest tests.test_retrieval -v - prints the 4 recall numbers and HIT/MISS per question (takes ~9 min).
Remember: Slower but better: search wide and cheap first, then let a careful reader pick the best few.
