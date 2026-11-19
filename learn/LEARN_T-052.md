# LEARN T-052 - A faster test suite
Built: A timing tool and three small helpers so slow, repeated setup happens once. The suite went from about 9 minutes to about 4.5.
Why this way: We fixed the waiting (an IPv6 try on every Ollama call, the same PDFs chunked five times). We did NOT shorten timeouts or skip tests, because that would make the tests prove less.
New words: fixture = setup that tests share; cache = a saved result reused instead of recomputed
Look at: tests/fast_localhost.py - one small change that saved about 2 minutes
Try it: python tools/test_times.py out.csv - a CSV with every test's seconds, slowest first
Remember: Measure first; the slowest test was slow for a reason nobody guessed.
