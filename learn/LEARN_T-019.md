# LEARN T-019 - Reading the medicine label and noticing when it changed
Built: A loader that reads the strengths (10, 20, 40 mg) from two saved versions of the Kerendia label (2021 and 2025), each with the exact XML spot it came from.
The agreement check now says "version change" when the same label changed over time, and "copy disagrees" when a copy differs from the original.
Why this way: A new label version is not an error, so it gets its own review kind instead of "conflict". We did NOT make copies that disagree count as conflicts: copies never count as proof, but silently ignoring them hid problems.
New words: SPL = the XML format of a drug label; set id = the label's permanent ID across versions; version change = same document, new version, different value.
Look at: ectd_engine/gate/agree.py - the order: conflict / version change first, then copy disagrees.
Try it: python -m ectd_engine.loaders.dailymed --dry-run - 5 lines, v1 has 10 and 20 mg, v12 adds 40 mg.
Remember: a changed label is news to flag, not a mistake to hide or to shout about.
