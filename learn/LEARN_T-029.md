# LEARN T-029 - The watcher waits longer and spots hidden writers
Built: The test run may now take up to 900 seconds (you can change it with --timeout N). If a file changed but the log never mentions it, the watcher raises a FLAG.
Why this way: A timeout prints "TIMEOUT - raise --timeout" and never says OK, so a slow suite cannot look like a pass. We did NOT just make the limit huge with no message, because a hung test would then wait forever unseen.
New words: timeout = the longest we wait before giving up; process tree = a program plus every program it started
Look at: tools/watch.py - check 6 in flags() compares changed files with .brain/activity.log
Try it: python tools/watch.py run "python -c \"import time; time.sleep(5)\"" --timeout 1 - you should see TIMEOUT - raise --timeout
Remember: If the watcher did not see a hand write a file, it says so.
