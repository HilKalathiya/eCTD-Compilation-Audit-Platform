"""Rough token estimate (chars/4) for files or folders, to keep Project knowledge small.

Usage: python tools/estimate_tokens.py handoff/brain handoff/PROJECT_INSTRUCTIONS.md
"""
import sys
from pathlib import Path

total = 0
for arg in sys.argv[1:] or ["."]:
    p = Path(arg)
    files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file() and x.suffix in {".md", ".txt", ".py", ".json"})
    for f in files:
        n = len(f.read_text(encoding="utf-8", errors="ignore"))
        total += n
        print(f"{n // 4:>8,} tokens  {f}")
print(f"{total // 4:>8,} tokens  TOTAL")
