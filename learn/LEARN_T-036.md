# LEARN T-036 - The watcher no longer shows green when git breaks
Built: watch.py now retries a failed git call 3 times. If git still fails it shows GIT ERROR and exits with 2.
It used to show "0 changed / FLAGS: none" when git hiccuped.
Why this way: we raise an error (GitError) instead of returning empty text. Alternative NOT chosen: keep returning empty text and add a warning line, because a missed warning still looks like a green check.
New words: GitError = our own error type for "git kept failing"; exit code = number a program returns (0 = fine, 2 = error)
Look at: tools/watch.py - git() retries, then raises; status() catches it
Try it: python -m unittest tests.test_watch.GitFailureTests -v - 8 tests, all ok
Remember: no answer is not the same as "nothing changed".
