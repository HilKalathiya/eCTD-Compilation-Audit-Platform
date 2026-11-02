"""Replays saved model drafts through the frozen validator and the ported one, and checks they agree."""
import csv
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FROZEN_DIR = ROOT / "writer_test"
OUT_DIR = FROZEN_DIR / "outputs" / "ollama_gemma4-e4b"
# Round-3 audit (160 drafts, 8 sections x 20) and the saved baseline drafts. Read-only.
DEFAULT_FILES = [OUT_DIR / "audit_20261029_135323.jsonl", OUT_DIR / "drafts.jsonl"]
DEFAULT_OUT = ROOT / "evidence" / "T-040" / "replay.csv"


class ReplayError(Exception):
    pass


class Judge:
    """One validator route: the four functions that decide a verdict."""

    def __init__(self, compute_facts, validate, render, verify_render):
        self.compute_facts, self.validate = compute_facts, validate
        self.render, self.verify_render = render, verify_render

    def verdict(self, task, text):
        """Return ('accepted'|'rejected', sorted list of problems), same steps as the audit run."""
        try:
            facts, flags, required = self.compute_facts(task)
            problems = self.validate(text, facts, flags, required) if text else ["empty output"]
            if not problems:
                problems = ["re-read: " + p for p in self.verify_render(self.render(text, facts), task)]
        except Exception as e:  # a crash is a verdict too, so it can be compared
            return "error", [f"{type(e).__name__}: {e}"]
        return ("rejected" if problems else "accepted"), sorted(problems)


def load_frozen():
    """Import writer_test/writer_test (relative imports inside) under a private name."""
    pkg = FROZEN_DIR / "writer_test"
    spec = importlib.util.spec_from_file_location("_frozen_wt", pkg / "__init__.py",
                                                  submodule_search_locations=[str(pkg)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_frozen_wt"] = mod
    spec.loader.exec_module(mod)
    from importlib import import_module
    f, v, r = (import_module(f"_frozen_wt.{n}") for n in ("facts", "validator", "rendercheck"))
    return Judge(f.compute_facts, v.validate, v.render, r.verify_render)


def load_port():
    from ectd_engine.validator.rendercheck import verify_render
    from ectd_engine.validator.validator import render, validate
    from ectd_engine.writer.facts import compute_facts
    return Judge(compute_facts, validate, render, verify_render)


def load_drafts(files):
    """Read every draft: (file name, line no, task_id, draft no, text). Missing file -> ReplayError."""
    rows = []
    for path in files:
        path = Path(path)
        if not path.is_file():
            raise ReplayError(f"draft file missing: {path}")
        n = 0
        with open(path, encoding="utf-8-sig") as fh:
            for i, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                r = json.loads(line)
                text = r["raw_draft"] if "raw_draft" in r else r["text"]
                rows.append((path.name, i, r["task_id"], r.get("draft"), text))
                n += 1
        if n == 0:
            raise ReplayError(f"draft file has no drafts: {path}")
    return rows


def load_tasks(path=None):
    path = Path(path) if path else FROZEN_DIR / "data" / "tasks.json"
    if not path.is_file():
        raise ReplayError(f"tasks file missing: {path}")
    with open(path, encoding="utf-8") as fh:
        return {t["task_id"]: t for t in json.load(fh)["tasks"]}


def replay(rows, tasks, frozen, port):
    """Return one result dict per draft."""
    out = []
    for src, line, task_id, draft, text in rows:
        if task_id not in tasks:
            raise ReplayError(f"{src} line {line}: unknown task_id {task_id}")
        fv, fp = frozen.verdict(tasks[task_id], text)
        pv, pp = port.verdict(tasks[task_id], text)
        out.append({"source": src, "line": line, "task_id": task_id, "draft": draft,
                    "frozen_verdict": fv, "port_verdict": pv,
                    "frozen_rules": " | ".join(fp), "port_rules": " | ".join(pp),
                    "same": "yes" if (fv, fp) == (pv, pp) else "no"})
    return out


def write_csv(results, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["source", "line", "task_id", "draft", "frozen_verdict", "port_verdict",
            "frozen_rules", "port_rules", "same"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(results)


def summary(results):
    same = sum(r["same"] == "yes" for r in results)
    return f"{len(results)} drafts, {same} same, {len(results) - same} different"


def main(argv=None, files=None, frozen=None, port=None, tasks=None, out=None):
    try:
        rows = load_drafts(files or DEFAULT_FILES)
        if not rows:
            raise ReplayError("no drafts found")
        results = replay(rows, tasks or load_tasks(), frozen or load_frozen(), port or load_port())
    except ReplayError as e:
        print(f"REPLAY ERROR: {e}")
        return 2
    write_csv(results, out or DEFAULT_OUT)
    for r in results:
        if r["same"] == "no":
            print(f"DIFFERENT {r['source']}:{r['line']} {r['task_id']} draft {r['draft']}: "
                  f"frozen={r['frozen_verdict']} {r['frozen_rules']!r} port={r['port_verdict']} {r['port_rules']!r}")
    print(summary(results))
    for f in (files or DEFAULT_FILES):
        print(f"  from {Path(f).name}: {sum(r['source'] == Path(f).name for r in results)} drafts")
    return 0 if all(r["same"] == "yes" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
