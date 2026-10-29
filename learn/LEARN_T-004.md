# LEARN T-004 - Only Hil is listed as contributor
Built: Told Claude Code not to add its name to commits, cleaned old commit messages of any
Claude co-author line, and made "push to GitHub" part of finishing every task.
Why this way: GitHub lists anyone in a Co-Authored-By line as a contributor. Old lines needed a
history rewrite plus one force-push (backup bundle kept outside the repo). From now on we
never force-push; a failed push is reported as a blocker instead of being overridden.
New words: co-author trailer = a Co-Authored-By line at the end of a commit message
           attribution setting = Claude Code option for the text it adds to commits (now empty)
Look at: .claude/settings.json - the "attribution" key with empty commit and pr
Try it: git log --all --format=%B | grep -i -c co-authored-by - should print 0
Remember: A task is finished only when it is saved online too.
