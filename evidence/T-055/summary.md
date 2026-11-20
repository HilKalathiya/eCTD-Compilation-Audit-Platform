# T-055 summary: flaky test hunt

Seconds = wall-clock from times.txt (includes Python start-up); "Ran" line is unittest's own time.

| run | tests | result | seconds | failing test |
|-----|-------|--------|---------|--------------|
| 1 | 614 | OK | 338 | - |
| 2 | 614 | OK | 297 | - |
| 3 | 614 | OK | 320 | - |
| 4 | 614 | FAIL (failures=1) | 322 | test_watch.WatchFlagTests.test_broken_input_writes_a_logerror_line (`AssertionError: 0 != 1`, tests/test_watch.py:274) |
| 5 | 614 | OK | 314 | - |

Runs 6-10 were NOT completed: run 6 was killed by Claude Code because the machine ran low on memory.
Its partial file was deleted. Result: 4 clean / 1 failed out of 5 finished runs. NOT "10 clean", NOT "not reproduced".

## What the failure was
The hook `watch.py log` was fed broken JSON. It should write one LOGERROR line into .brain/activity.log.
In run 4 the log had 0 lines. The dots in run4.txt run unbroken up to the F, so the hook printed nothing.
The old test threw away the hook's exit code and stderr, so the cause is NOT proven. Two candidates:
(a) the log write raised and the old `except: pass` hid it (exit 0);
(b) the child process died at start-up under load (non-zero exit).

## Reproduction attempts
540 single-test loops (3 then 6 in parallel): the run-4 failure did not reproduce.
One different error appeared once (loop b #60): `setUpClass` failed, `git commit -q -m base failed 3x, exit 1`
with empty stderr. That is a separate possible flake (git_retry), seen once, not fixed here.

## What was changed (no retry, sleep, skip or longer timeout added)
- watch.py: `status --tests` now prints `FAILING TEST: <name> -> <last traceback line>` for each FAIL/ERROR.
- watch.py: if even the LOGERROR line cannot be written, the hook now says so on stderr (was silent).
- tests: planted tests for both; run_hook now keeps exit code + stderr and shows them if the test fails again.
Next time it fails, the message says whether it was (a) or (b).
