# LEARN T-004 - Only Hil is listed as contributor
Built: Told Claude Code not to add its name to commits, and cleaned old commit messages
of any "Co-Authored-By: Claude" line. A backup bundle of the old history sits outside the repo.
Why this way: GitHub lists anyone in a Co-Authored-By line as a contributor. We rewrote history
(changes every commit ID) instead of leaving old lines, so we need a force-push; we did NOT
use plain --force because --force-with-lease refuses if someone else pushed meanwhile.
New words: co-author trailer = a "Co-Authored-By:" line at the end of a commit message
Look at: .claude/settings.json - the new "attribution" key with empty commit and pr
Try it: git log --all --format=%B | grep -i -c co-authored-by - should print 0
Remember: Rewriting history is safe only with a backup and a careful push.
