"""Print one section of a big archive document, so nobody reads the whole file.

Usage:
  python tools/section.py explainer 13        # explainer section 13 (numbered '## 13. ...')
  python tools/section.py explainer list      # list all section titles
  python tools/section.py brief 6             # technical brief section 6
  python tools/section.py explainer grep Q3B  # lines containing text (max 40, with section number)
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATES = [HERE.parent / "handoff" / "archive", HERE.parent / "archive", HERE.parent]
FILES = {"explainer": "explainer_full.md", "brief": "technical_brief.md",
         "problems": "problems_and_solutions.md", "models": "model_choice_and_costs.md"}


def find(name):
    for d in CANDIDATES:
        p = d / FILES[name]
        if p.exists():
            return p
    sys.exit(f"cannot find {FILES[name]} in {[str(c) for c in CANDIDATES]}")


def sections(text):
    parts = re.split(r"(?m)^(?=## )", text)
    return [p for p in parts if p.startswith("## ")]


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    name, arg = sys.argv[1], sys.argv[2]
    if name not in FILES:
        sys.exit(f"unknown doc {name!r}; choose from {list(FILES)}")
    text = find(name).read_text(encoding="utf-8")
    secs = sections(text)
    if arg == "list":
        for s in secs:
            print(s.splitlines()[0])
    elif arg == "grep":
        needle = (sys.argv[3] if len(sys.argv) > 3 else "").lower()
        shown = 0
        for s in secs:
            title = s.splitlines()[0]
            for line in s.splitlines()[1:]:
                if needle and needle in line.lower():
                    print(f"[{title[:40]}] {line[:200]}")
                    shown += 1
                    if shown >= 40:
                        return
    else:
        hit = [s for s in secs if re.match(rf"## {re.escape(arg)}[. ]", s)]
        if not hit:
            sys.exit(f"no section {arg}; try: list")
        print(hit[0].rstrip())


if __name__ == "__main__":
    main()
