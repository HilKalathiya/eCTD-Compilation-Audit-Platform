"""Replays every saved T-064/T-065 P.8.3 draft through the current validator and compares each verdict and problem list with the saved one (read-only)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from ectd_engine.stability import facts as F, loop  # noqa: E402

RUNS = [("T-064/direct", False), ("T-064/skill", False), ("T-065/direct/run1", True), ("T-065/retry/run1", True), ("T-065/skill/run1", True)]


def main():
    total = same = 0
    for name, heldout in RUNS:
        rows = F.load_rows(ROOT / "evidence" / "T-065" / "heldout.csv") if heldout else F.load_rows()
        tasks = {t["task_id"]: t for t in loop.make_tasks(F.p83_facts(rows, heldout))}
        t_total = t_same = 0
        for line in (ROOT / "evidence" / name / "results.jsonl").read_text(encoding="utf-8").splitlines():
            res = json.loads(line)
            task = tasks[res["task_id"]]
            for d in res["drafts"]:
                problems, _ = loop.draft_problems(d["text"], task)
                t_total += 1
                t_same += int((not problems) == bool(d["passed"]) and problems == d["problems"])
        print(f"{name}: drafts {t_total}, same verdict and problems {t_same}, different {t_total - t_same}")
        total += t_total
        same += t_same
    print(f"TOTAL drafts {total}, same {same}, different {total - same}")
    return 0 if total == same else 1


if __name__ == "__main__":
    sys.exit(main())
