# LEARN T-021 - Shelf life from the confidence bound
Built: Code that draws the best straight line through stability results, then finds the month where the safe edge of that line meets the spec limit.
It also holds a Decimal "t table" so no outside maths library is needed.
Why this way: Regulators (ICH Q1E) ask where the one-sided 95% bound crosses the limit, not where the line does; the line always promises a longer life than the data can support (the test prints both).
One-sided because only one direction matters: assay falling below its minimum, impurity rising above its maximum. We did NOT use the plain line because it ignores how uncertain the line is.
The cap (2 x longest month, or longest + 12) stops us from promising a life far beyond what was tested.
New words: confidence bound = edge of the range where the true average line probably lies; extrapolation = predicting past the last tested month; residual SD = typical gap between points and the line; t quantile = the multiplier that sets how wide the bound is.
Look at: ectd_engine/stats/q1e.py - `Fit.bound` is the whole idea in 4 lines.
Try it: python -m unittest tests.test_q1e -v - you see "line 25.08 months vs bound 24.38 months".
Remember: The bound, not the line, decides the shelf life, and the cap limits how far you may go.
