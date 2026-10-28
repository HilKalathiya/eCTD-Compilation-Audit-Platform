# FIRST CHAT — exactly what to paste (in order)

Before this: finish steps 1–3 in `00_READ_FIRST.md` (Instructions pasted, 8 files uploaded, folder `E:\E\Project` already prepared for Claude Code).
If the new project chat lets you connect a folder, connect `E:\E\Project` (Add folder). Then the brain can watch Claude Code directly. If not, you use the clipboard method in Message 2. Both work.

---
## Message 0 — OPTIONAL: let the brain read the whole explainer once
Skip this unless you want it. Cost: about 54,000 tokens once. Never put the explainer in project Knowledge (it would be re-read in every chat).
Attach `handoff\archive\explainer_full.md` to this one message and paste:
```
Read the attached explainer once. Do not summarise it back to me.
Reply in at most 20 lines with only: (1) anything that contradicts your brain/01-04 files, (2) the 5 facts a task-card writer must remember that are missing from brain/01-04, one line each.
I will not attach it again; I will paste single sections when you say "NEED §n".
```
Then append the 5 facts to `brain\01_design_on_one_page.md` (re-upload it).

---
## Message 1 — THE PLANNER (this is the real first instruction)
```
You are the brain of my project (your instructions and the brain/ files are loaded).
Job 1: build the final master plan.
- Read brain/01-06. The draft master plan is in brain/04.
- Attack the draft: wrong order, missing chunks, chunks bigger than 2 sessions, any chunk without a planted-error test, anything that breaks the design rule.
- Reply in at most 45 lines: (a) the final chunk list in order, one line each: id, what, "done when"; (b) the 3 biggest risks; (c) up to 3 questions for me, only decisions I must make; (d) then TASK CARD T-001.
No research. No long explanations. Plain words: I am a student, not a regulatory expert.
```
Answer its questions in one short message. Save its final plan: replace `brain\04_plan_and_next_steps.md` with it and re-upload.

---
## Message 2 — HOW WE WORK AND HOW THE BRAIN WATCHES THE HANDS
```
How we work from now on.
1. You give me one TASK CARD. I paste it into Claude Code (terminal in E:\E\Project).
2. When it finishes I paste its REPORT here.
3. You never trust the REPORT. If you can run commands in my folder, run `python3 tools/watch.py status --tests` and the ACCEPT commands yourself. If you can't, say so and I will paste the output of `python tools/watch.py status --tests | clip`.
4. Read FLAGS first. Verdict: PASS / FIX / REPLAN, then the next card.
5. If you need a part of the explainer, say "NEED §n" and I will paste that section only.
Confirm in 5 lines: can you run commands in my folder (yes/no), and how you will watch Claude Code.
```

---
## Message 3 — TEACHING MODE (paste once, right after Message 2)
```
I am a beginner in coding. From now on: every card has a plain-words WHY; every verdict ends with "In plain words:" (2 lines); at the end of each phase give me a recap of at most 10 lines with everyday analogies and every technical term explained. Keep it short; tokens are limited.
```

## Start Claude Code (once per task)
Open a terminal in `E:\E\Project`, run `claude`, and type:
```
Read CLAUDE.md and STATE.md. Then wait for a TASK CARD. Do nothing else.
```
Then paste the card. Type `/clear` before each new card (saves tokens).
To follow along: second terminal in `E:\E\Project`, run `python tools/watch.py live` (plain-English feed). In Claude Code type `/where`, `/explain` or `/recap` any time. After each task read `learn\LEARN_<task>.md`.

## Every task after that
1. In the project chat say `next` -> you get a card.
2. Paste the card into Claude Code. Wait for its REPORT.
3. Paste the REPORT into the project chat. If the brain says it cannot see your folder, also run `python tools/watch.py status --tests | clip` and paste.
4. Brain answers PASS / FIX / REPLAN + next card.

## What the brain knows without the explainer
`brain/01` design (1 page) · `02` decisions · `03` test results · `04` plan · `05` you · `06` file map · `07` history. Everything deeper is in the explainer, one section at a time: `python tools/section.py explainer list` shows all 38 titles.
