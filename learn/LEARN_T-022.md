# LEARN T-022 - Can the batches share one line?
Built: A test that asks "do all batches fade at the same speed, and start at the same level?" and then gives the shelf life from the right model.
Why this way: Q1E uses 0.25, not 0.05, because a weak test would miss real differences and let a bad batch hide in the average (over-claimed shelf life). Slopes come first: if speeds differ, the starting levels do not matter. We did NOT just pool everything: it gives a longer shelf life but can be wrong.
New words: ANCOVA = compares lines of several groups at once; p-value = chance of a gap this big if the batches were really the same; pooling = fitting one line to all batches.
Look at: ectd_engine/stats/pool.py - decide() is the whole rule in 5 lines; p equal to 0.25 is NOT pooled.
Try it: python -m unittest tests.test_pool -v - 12 tests OK, including "forcing full pooling gives a longer shelf life".
Remember: Pool only when the data say batches look alike; otherwise the weakest batch sets the shelf life.
