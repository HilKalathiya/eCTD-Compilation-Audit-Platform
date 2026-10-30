---
name: verify
description: Run the watch tool and the full tests, then report FLAGS and test result in 3 plain lines
disable-model-invocation: true
allowed-tools: Bash(python tools/watch.py *)
---

Run `python tools/watch.py status --tests`. Then report in 3 plain lines: (1) the FLAGS line, (2) the test result (Ran N tests, OK or FAILED), (3) what Hil should do next. Report only what the command printed; never guess.
