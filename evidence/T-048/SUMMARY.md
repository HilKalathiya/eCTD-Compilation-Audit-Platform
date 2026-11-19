# T-048 summary: required outside-count sentence + exact prompt pattern (Gemma gemma4:e4b)

- Real windows: 129 / 130 accepted; re-read wrong = 0; 105 accepted on the first draft; 162 drafts / 129 accepted paragraphs (166 drafts / 130 windows overall). Details: audit.csv, summary.md (its title still says T-047; the audit tool was read-only).
- Synthetic windows (n_outside > 0, declared-basis attributes only, limit moved onto one of the window's own results): 21 / 26 accepted; re-read wrong = 0; 9 first-try; 61 drafts / 26 windows. Files: run/p56_ollama_gemma4-e4b/synthetic/.
- Rejects by rule, synthetic (5 windows, each broke 4 rules together because the model wrote a number word instead of [[n_outside]]):
  - number written as a word: "Nine of [[n_batches]] results were outside the limit." (s013)
  - missing required facts [n_outside] / missing outside-count sentence: "Twelve of [[n_batches]] results were outside the limit." (s019)
  - failure wording without [[n_outside]]: "One batch of [[n_batches]] results were outside the limit." (s010)
- Rejects by rule, real: 1 window (w103) wrote "based on [[basis]]" (source wording) in all 4 drafts.
- T-047 replay: all 520 old drafts through the new validator -> 0 accepted (the new rule fired on all 520; nothing loosened).
- Mutation test: all kinds caught 100%, including omit_outside_statement; correct text accepted 100%.
- blind.csv: 25 rows (22 real + 3 planted), made from the 130 real windows only. Synthetic windows are NOT in it (they live in their own folder and are marked "synthetic": true in synthetic/tasks.json).
- Run log: run_log.txt.
