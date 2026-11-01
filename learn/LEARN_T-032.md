# LEARN T-032 - the log no longer loses commands, and re-runs are fast
Built: The logging hook now survives a broken character in a command, and writes a LOGERROR line if anything else goes wrong.
The reranker now remembers each score on disk, so a second test run does not repeat the slow work.
Why this way: We could have just skipped lines that fail, but a silent gap is what caused the false FLAGS. A LOGERROR line makes the gap visible.
We did NOT keep scores in memory only: that is lost when the test run ends, so every run would be slow again.
New words: lone surrogate = half of a two-part character, which UTF-8 cannot write; cache = saved answers reused later; cache key = fingerprint that decides if a saved answer still fits
Look at: ectd_engine/knowledge/rerank.py - the key mixes model name, version, question and passage text, so any change = fresh score.
Try it: python -m unittest tests.test_retrieval.RerankCacheTests - 6 tests pass, no model needed.
Remember: A check that fails silently is worse than one that fails loudly.
