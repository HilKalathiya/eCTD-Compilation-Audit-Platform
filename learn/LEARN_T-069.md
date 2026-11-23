# LEARN T-069 - A number can no longer hide in a guideline name
Built: A closed list of the exact guideline names and section numbers that may appear without being counted as numbers.
Anything else with a digit, like "per Q48", must now be placed or it fails.
Why this way: We did NOT keep a pattern ("Q followed by digits") and block bad ones, because a pattern lets new tricks through. A whole-token list lets in only what we named.
The cross-check also pairs numbers by value, so one extra number is one failing row and cannot shift the rest.
New words: allowlist = a closed list of what is permitted; full match = the whole token must equal an entry; unplaced = a number with no fact behind it.
Look at: ectd_engine/references/registry.py - the list is built from the plans in code.
Try it: python -m unittest tests.test_exempt_tokens - should say OK (7 hidden numbers fail, 4 real citations pass).
Remember: Allow only what you can name, never what merely looks right.
