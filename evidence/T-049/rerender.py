"""Re-renders every accepted T-048 paragraph with the T-049 renderer (no model) and writes them to rendered.md."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RUN = ROOT / "evidence" / "T-048" / "run" / "p56_ollama_gemma4-e4b"


def accepted_text(result):
    """The text of the draft that passed (the last passing draft), or None."""
    passed = [d["text"] for d in result["drafts"] if d["passed"]]
    return passed[-1] if passed else None


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def rerender_all(live):
    """[(task_id, task, new paragraph)] for every accepted window, real first then synthetic. live = {mdd: {column: Justification}}."""
    from ectd_engine.writer.spec_facts import compute_spec_facts, q3b_row_quote, render_paragraph
    out = []
    for folder in (RUN, RUN / "synthetic"):
        with open(folder / "tasks.json", encoding="utf-8") as f:
            tasks = {t["task_id"]: t for t in json.load(f)["tasks"]}
        for res in load_jsonl(folder / "results.jsonl"):
            text = accepted_text(res) if res["accepted"] else None
            if text is None:
                continue
            task = dict(tasks[res["task_id"]])
            if task["basis"] == "q3b_qualification":
                task.setdefault("mdd", "40")
                j = live[task["mdd"]][task["column"]]
                task.update(q3b_quote=q3b_row_quote(task["mdd"]), q3b_page=str(j.page), q3b_version=j.doc_version)
            facts, _, _ = compute_spec_facts(task)
            out.append((task["task_id"], task, render_paragraph(text, facts, task["basis"])))
    return out


def main(dest):
    sys.path.insert(0, str(ROOT))
    from tests.test_mutation_spec import live_data
    items = rerender_all(live_data())
    lines = [f"# T-049 re-rendered T-048 paragraphs ({len(items)})", ""]
    for tid, task, para in items:
        lines += [f"## {tid}", para, ""]
    Path(dest).write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(items)} paragraphs -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).with_name("rendered.md")))
