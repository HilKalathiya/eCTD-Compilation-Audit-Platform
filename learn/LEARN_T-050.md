# LEARN T-050 - Counts as digits and verbs that agree
Built: Code now writes every count as digits and picks "was" or "were" from the number ("1 of 24 results was").
Why this way: Code fixes any odd words before the basis, instead of listing each bad phrase one by one (that list never ends).
New words: agreement = the verb matches the number (1 was, 2 were)
Look at: ectd_engine/writer/spec_facts.py - BASIS_LEAD and render_paragraph
Try it: python evidence/T-050/rerender.py - you should see 150 paragraphs and 0 hits on every rule
Remember: A rule that cannot fail proves nothing, so every new rule got a planted test.
