# LEARN T-027 - Guideline pages cut into quotable pieces
Built: Five ICH guideline PDFs are cut into small pieces ("chunks"). Each piece remembers its document, version, page and (for tables) table id.
Why this way: Small pieces let a search find one paragraph and a reviewer open the exact page. Tables are kept whole (cut only between rows) because half a table loses its meaning.
kb_chunks has no number columns on purpose: guideline numbers are quotes, not facts. Alternative NOT chosen: put thresholds into the facts table; they would then look checked by the gate when they are only quoted text.
New words: chunk = a small piece of text cut from a document; table_id = name of a table on a page, like p11-t2; borderless table = a table with no drawn lines
Look at: ectd_engine/knowledge/chunk.py - borderless_tables() finds tables by gaps between words
Try it: python -m ectd_engine.knowledge.load --dry-run - one line per guideline with chunk and table counts
Remember: A quote must carry its page, and a table must stay whole.
