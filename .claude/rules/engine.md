---
paths:
  - "ectd_engine/**"
---
# Engine rules (load only for ectd_engine/**)
Use `decimal.Decimal` with `ROUND_HALF_UP` to the specification's decimals (never Python `round()`).
Decimal only: no `float()`, no `round()`. Values come only through the fact-store API.
