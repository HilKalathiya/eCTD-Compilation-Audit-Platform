# LEARN T-056 - The same document as a Word file, checked again after saving
Built: P5.docx is written from the same plan and placements as the HTML. Then the saved file is opened again and every number in it is counted and compared.
Why this way: One shared reading order (walk) feeds both HTML and Word, so there is no second path that could drift. We did NOT trust the objects in memory: a person can edit a saved Word file, so only the file itself is checked.
New words: re-read check = open the saved file again and test its content; planted error = a mistake we add on purpose to see if a check catches it.
Look at: ectd_engine/render/docx.py - reread() uses only the file, never the writer's variables.
Try it: python -m unittest tests.test_render_docx - 10 tests, OK (3 planted edits caught).
Remember: A check that only looks at what we meant to save proves nothing about what was saved.
