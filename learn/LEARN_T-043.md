# LEARN T-043 - Where does each spec limit come from?
Built: code now turns each Lek acceptance criterion into a checked fact and says where it came from. It also writes the P.5.1 table and works out the P.5.6 facts (cited ICH Q3B quote, batch support).
Why this way: Q3B limits are computed from our tested table at an assumed 40 mg/day; typed limits are marked DECLARED so they never look sourced. Not chosen: typing 0.5 into the spec file, because a typed number can silently disagree with Q3B.
New words: MDD = maximum daily dose; TDI = total daily intake of an impurity; NMT/NLT = not more than / not less than.
Look at: ectd_engine/specs/load.py - a q3b row with a typed value is refused, and so is a declared row that claims a source.
Try it: python -m ectd_engine.specs.p56 - prints the P.5.1 table, the Q3B quote with page 11, and n/min/max/outside per attribute.
Remember: a limit is only as trustworthy as its traced basis; "declared" must always say so.
ChemR answer: (b)(4) - FDA Chemistry Review 215341Orig1s000ChemR.pdf hides the drug-product limits (107 "(b)(4)" marks; e.g. page 28 reads "NLT  % (Q) in  min"). No numeric NMT/NLT limit is visible on any page.
