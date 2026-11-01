# LEARN T-030 - the watcher now keeps whole commands and wants real proof of writing
Built: The activity log no longer cuts commands short. The "changed with no logged action" alarm now needs proof that a file was really written.
Why this way: We look for write words (like `>`, `tee`, `Copy-Item`) right before the file name. The alternative, "any mention counts", was fooled by a plain `cat file`.
New words: write evidence = a logged step that really wrote a given file; exit code 124 = the usual number for "ran out of time".
Look at: tools/watch.py - `command_writes` lists the write patterns one per line.
Try it: python -m unittest tests.test_watch -v - all 20 tests say ok.
Remember: Reading a file is not writing it, and the alarm must know the difference.
