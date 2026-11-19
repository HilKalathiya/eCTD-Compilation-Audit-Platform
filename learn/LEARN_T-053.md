# LEARN T-053 - Code decides the document and tags every number
Built: A plan (which sections, which facts each needs) and a builder that writes the P.5 HTML. Each number in the page is tagged with the fact it came from.
Why this way: We count every number in the output and compare with the tags. We did NOT trust the writer to say "all numbers are placed", because a bare 0.7% would slip through.
New words: placement = a record saying which fact one number came from; exempt token = a number-like thing (batch id) allowed without a fact
Look at: ectd_engine/render/numbers.py - the short, explicit list of exempt tokens
Try it: python tools/render_doc.py --out evidence/T-053/ - report with numbers equal to placements and missing 0
Remember: If a number has no tag, the page is rejected.
