# T-052 changes (seconds from before.csv -> after.csv; 581 tests both times, 0 skipped, no assert line removed)

Suite wall time: 555.8 s -> 266.4 s (`tools/test_times.py`, includes class setup).

Three setup helpers, no assertion touched. Each is imported by the test modules that need it:
- `tests/fast_localhost.py`: "localhost" resolves to IPv4 only. Windows tried ::1 first and Ollama waits about 2 s per new connection (32 questions x 2 connections in the gold test).
- `tests/chunk_cache.py`: the five guideline PDFs are chunked once per run (about 12 s); every caller gets a deep copy. The cost now sits in the first class setup that needs the chunks, so tests that follow show about 0 s.
- `tests/warm_models.py`: torch and sentence_transformers are imported in a background thread while the database tests wait on sockets.

| Test | Old s | New s | What changed |
|---|---|---|---|
| test_citations.GoldCitationTests.test_gold_top1_first_200_chars_verify | 64.9 | 2.6 | fast_localhost (Ollama connections) |
| test_retrieval.RetrievalTests.test_planted_reversed_reranker_drops_below_vector | 63.6 | 2.0 | fast_localhost |
| test_demo_facts.DemoFactsLive.test_demo_command_exits_0_with_5_proof_lines | 54.5 | 43.7 | none by me (about 10 s noise); the 10 000 database writes of the demo are engine work |
| test_demo_facts.DemoFactsLive.test_planted_edit_in_graph_fails_proof_5_and_exit_1 | 46.5 | 46.7 | none (needs its own demo run) |
| test_migrate.MigrateTests.test_rerun_with_xml_fact_present | 46.2 | 48.3 | none (needs its own demo run) |
| test_retrieval.RerankLiveTests.test_live_model_ranks_the_obvious_pair_first | 30.7 | 4.2 | warm_models (the 26 s import overlaps the demo tests) |
| test_ich_chunks.SymbolAndHeaderTests.test_running_headers_are_found_and_absent_from_chunks | 16.3 | 0.9 | chunk_cache |
| test_ich_chunks.SymbolAndHeaderTests.test_no_private_use_code_is_left_in_any_chunk | 13.7 | 0.0 | chunk_cache |
| test_ich_chunks.IchChunkTests.test_dry_run_prints_counts | 11.4 | 0.0 | chunk_cache |
| test_db_down.* (6 tests, 5.0 s each) | 5.0 | 5.0 | none: they wait for the real 5 s connect timeout, which is what they check |

Also changed (not in the slowest 15, needed for margin): `tests/test_watch.py` `WatchFlagTests` now builds its starting repo once in `setUpClass` and each test gets a copy (`shutil.copytree`) instead of 6 git calls plus one `watch task` each. The 30 tests together: 35.5 s -> 15.9 s. Their bodies and asserts are unchanged.

Not changed: the three demo runs (about 140 s of the 266 s). Each loads about 10 000 facts into Postgres and Neo4j and sits inside `ectd_engine/` (off limits), and the three tests need different things from a run (command line, tamper, then migrate).
