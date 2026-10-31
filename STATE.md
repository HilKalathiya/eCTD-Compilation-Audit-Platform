# STATE (newest first; Claude Code keeps this <= 40 lines; Hil re-uploads it to the Claude Project after each milestone)

## 2026-10-31 — K6 done
- Engine rules (Decimal only, no `float()`/`round()`, values via fact-store API) moved from CLAUDE.md to `.claude/rules/engine.md` (`paths: ectd_engine/**`). CLAUDE.md now has one pointer line. 5 tests in `tests/test_rules.py`.

## 2026-10-31 — T-027 (C2.1) done
- ICH Step-4 PDFs (M4Q(R1), Q1A(R2), Q1E, Q3B(R2), Q6A) in `data/public/ich/` (SOURCES.md has URL, date, sha256). `ectd_engine/knowledge/chunk.py`: ~800-char text chunks on paragraph/heading boundaries (never across pages); tables as one chunk each (ruled via find_tables, borderless via word gaps), cut only between rows if > 1500 chars; ids `<doc>:p<page>-c<n>` / `table_id p<page>-t<n>`; Symbol-font characters (≤ ≥ ±) mapped to real ones.
- Migration 006 `kb_chunks` (no value column; page is the only number). `python -m ectd_engine.knowledge.load [--dry-run]`; reload is idempotent. 21 tests in `tests/test_ich_chunks.py` (3 Q3B threshold tables complete; planted missing row / page 0 / no doc refused; live reload no duplicates). Q1E has no real table: its decision tree (p12) is a drawing, kept as text chunks.

## 2026-10-30 — T-026 (C1 fix) done
- `migrate` now records each migration file in table `schema_migrations` (filename, sha256, applied_at) and runs only unrecorded files, each in its own transaction. An old DB without the table gets 001-004 recorded without re-running. A recorded file whose text changed -> error "migration edited after it ran". Migration 005 creates the table. The T-025 CheckViolation bug is fixed; `demo_facts` now migrates first, then wipes only its own rows. `tests/test_migrate.py`: 3 live tests (incl. planted edit).

## 2026-10-30 — T-025 (A0) done
- `python -m ectd_engine.demo_facts` loads Lek (4965 accepted, 60 quarantined), Kerendia PDF (8) and DailyMed label (5) into live Postgres + Neo4j through the gate under the id prefix `DEMO25-` (nothing else is touched), plants one bad Lek row, prints 5 PROOF lines (Lek CSV row, Kerendia page+box, label version change v1 20 mg vs v12 40 mg, planted row quarantined, compare() == []); exit 0 only if all hold. `--clean` removes the demo data. ~70 s.
- 3 live tests in `tests/test_demo_facts.py` (databases down -> FAIL "start Docker"; planted graph edit -> proof 5 fails, exit 1). Known bug (not fixed, needs a card): `migrate` re-run fails with CheckViolation when rows with `xml=`/`typed=` locators exist, because migration 002 re-adds the older locator rule before 004; the demo wipes its rows before migrating and the test cleans up.

## 2026-10-30 — T-024 done
- Outside check: `tests/test_r_crosscheck.py` (9 tests) runs R expirest 0.1.7 via `tests/r/q1e.R`: pooling decision equal for cases a/b/c, shelf life (and per-batch) equal within 0.01 month; single-batch assay (lower) and impurity (upper) too. NIST Norris.dat: slope, intercept, residual SD match to 15 digits.
- Flaky hunt: full suite 6 runs, 0 failures, no random/time use in tests. R 4.6.1 installed with winget; expirest lives in the per-user folder Documents-independent `~/R/win-library/4.6` (the test sets R_LIBS_USER itself). Missing R makes the test FAIL ("install R"). expirest does not apply our extrapolation cap; all cases are uncapped.

## 2026-10-30 — K5 done
- `/where`, `/explain`, `/recap` moved to `.claude/skills/<name>/SKILL.md` (text unchanged, disable-model-invocation true); new `/verify` (allowed-tools only `Bash(python tools/watch.py *)`) runs `watch.py status --tests`. `.claude/commands/` removed. 8 tests in `tests/test_skills.py`. Restart Claude Code to see the 4 skills.

## 2026-10-30 — T-023 done
- `ectd_engine/stats/oot.py`: `check(history, (month, value), level=0.99)` -> OK | OOT (with low/high) | NotEnoughData (< 3 points or all same month); uses the two-sided PREDICTION interval (`interval`). `check_with_policy` returns (result, note).
- `ectd_engine/stats/loq.py`: `parse` ("<LOQ", "<0.05", "ND" -> Below), `Policy` EXCLUDE (default) / REPORT_ONLY / SUBSTITUTE (needs value + reason, else ValueError), `apply_policy`, `shelf_life_with_policy` -> (ShelfLife or None, note). 22 tests in `tests/test_oot_loq.py`; PI matches statsmodels to 10 digits. q1e.py/tdist.py unchanged. Suite 226 OK.

## 2026-10-30 — T-022 done
- `ectd_engine/stats/pool.py`: `poolability(batches, spec_min, spec_max)` -> decision ("separate" / "common slope, separate intercepts" / "fully pooled"), `p_slope`, `p_intercept`, shelf life (separate = shortest batch; common slope = pooled error, df N-k-1, own intercepts; pooled = `shelf_life` on all points). `decide()` pools only if p > 0.25. `tdist.f_cdf` added (general incomplete beta). q1e.py unchanged (only called; `_one_side` reused).
- 12 tests in `tests/test_pool.py`; p-values match statsmodels anova_lm to 10 digits (cases a/b/c).

## 2026-10-30 — T-021 done
- `ectd_engine/stats/tdist.py`: Student t cdf/quantile in Decimal (incomplete beta, bisection; checked vs t-table and scipy). `q1e.py`: `fit`, `Fit.bound(month, side)` (one-sided 95% bound of the mean line), `shelf_life(points, spec_min, spec_max, cap_months)` solved to 0.01 month (half-up), cap = min(2 x longest, longest + 12) with `capped` + reason; `line_shelf_life` is the wrong-way comparator for tests only.
- Matches statsmodels to 10 digits (slope, intercept, bound); shelf life within 0.01 month. `requirements-dev.txt` pins statsmodels 0.15.0 + scipy 1.13.1 (test-only). Poolability stays C1.11.

## 2026-10-30 — K4 done
- Output style `Plain words` (`.claude/output-styles/plain-words.md`, 5 rules, keep-coding-instructions true) set via `"outputStyle": "Plain words"` in `.claude/settings.json` (exact case; hooks, deny list, attribution untouched). 7 tests in `tests/test_output_style.py`. Restart Claude Code, then `/output-style`.
