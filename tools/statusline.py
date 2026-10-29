"""Prints the one-line gauge at the bottom of Claude Code: task id, context %, cost, 5-hour limit %."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dig(data, *keys):
    for k in keys:
        if not isinstance(data, dict) or k not in data:
            return None
        data = data[k]
    return data


def _num(value, fmt):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "-"
    return fmt.format(value)


def task_id():
    try:
        with open(os.path.join(ROOT, ".brain", "task.json"), encoding="utf-8") as f:
            tid = json.load(f).get("id")
        return str(tid) if tid else "-"
    except Exception:
        return "-"


def render(raw):
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    ctx = _num(_dig(data, "context_window", "used_percentage"), "{:.0f}%")
    cost = _num(_dig(data, "cost", "total_cost_usd"), "${:.2f}")
    limit = _num(_dig(data, "rate_limits", "five_hour", "used_percentage"), "{:.0f}%")
    return f"{task_id()} | ctx {ctx} | cost {cost} | 5h {limit}"


def main():
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        print(render(raw))
    except Exception:
        print("- | ctx - | cost - | 5h -")
    return 0


if __name__ == "__main__":
    sys.exit(main())
