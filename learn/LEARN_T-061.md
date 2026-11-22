# LEARN T-061 - Look for real stability data before building on it
Built: Only a list (inventory.md) of where stability data might be. No code, because I could not confirm any public stability results.
Why this way: We did NOT write a stability loader first. If the data does not exist, the code would sit on invented numbers, which breaks the "code never invents a value" rule.
New words: inventory = a checked list of what files hold; time point = one test date (e.g. month 6) in a stability study
Look at: evidence/T-061/inventory.md - the row for the FDA chemistry review is marked NOT CHECKED
Try it: grep -c -i stability data/public/kerendia/kerendia_spl_v1.xml - prints 0
Remember: Say plainly what you could not check.
