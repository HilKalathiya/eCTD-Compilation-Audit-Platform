# Writer test: ollama / gemma4:e4b

| Measure | Result |
| --- | --- |
| Sections | 8 |
| Passed on the first draft | 6 of 8 |
| Passed within 4 drafts | 8 of 8 |
| Drafts per section (mean) | 1.4 |
| Seconds per section (mean) | 11 |
| Seconds per section (slowest) | 20 |
| Generation speed (tokens/s, median) | 14.5 |
| Prompt reading speed (tokens/s, median) | 1429.8 |
| Total wall time | 1.4 min |

Why drafts failed:

- number written as a word: 2
- does not state that a result is out of specification: 1

Per section:

| Task | Drafts | Passed | Seconds |
| --- | --- | --- | --- |
| lt_assay | 1 | yes | 10 |
| lt_total_impurities | 1 | yes | 9 |
| lt_impurity_a | 1 | yes | 8 |
| lt_dissolution | 3 | yes | 20 |
| lt_water | 1 | yes | 8 |
| acc_total_impurities | 1 | yes | 9 |
| acc_assay | 1 | yes | 10 |
| acc_impurity_b_oos | 2 | yes | 15 |
