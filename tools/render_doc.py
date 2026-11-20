"""Builds the P.5 document (P5.html, placements.jsonl, report.txt) from the accepted paragraphs of T-042 (P.5.4) and T-048 (P.5.6); no model."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RUN54 = ROOT / "evidence" / "T-042" / "run" / "p54_ollama_gemma4-e4b"
RUN56 = ROOT / "evidence" / "T-048" / "run" / "p56_ollama_gemma4-e4b"


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def accepted_text(result):
    """The text of the last draft that passed, or None."""
    passed = [d["text"] for d in result["drafts"] if d["passed"]]
    return passed[-1] if result["accepted"] and passed else None


def tasks_of(folder):
    with open(folder / "tasks.json", encoding="utf-8") as f:
        return {t["task_id"]: t for t in json.load(f)["tasks"]}


def live_data():
    """{mdd text: {column: Justification}} from the real loader, spec and Q3B check."""
    from decimal import Decimal
    from ectd_engine.specs import load, p56
    from ectd_engine.writer.batch_facts import LoaderStore
    store, live = LoaderStore(), {}
    for m in ("40", "5", "500"):
        spec = load.load(mdd=Decimal(m))
        live[m] = {r.attribute: j for r, j in zip(spec.rows, p56.compute(spec, store))}
    return live, store


def build_all():
    """Every task of both parts, built and checked. Returns (html, placements, report)."""
    from ectd_engine.render.html import build_document
    return build_document(build_items())


def build_items():
    """The checked sections of every task of both parts (the one input of the HTML and the Word writer)."""
    from ectd_engine.render.html import build_p54, build_p56
    from ectd_engine.writer.batch_facts import compute_batch_facts
    from ectd_engine.writer.spec_facts import compute_spec_facts, q3b_row_quote
    live, store = live_data()
    items = []
    t54 = tasks_of(RUN54)
    for res in load_jsonl(RUN54 / "results.jsonl"):
        text = accepted_text(res)
        if text is None:
            continue
        task = t54[res["task_id"]]
        facts, flags, _, table = compute_batch_facts(task, store.get, store.known_batches)
        items.append({"part": "3.2.P.5.4", "task_id": task["task_id"], "attribute": task["attribute"],
                      "batch_ids": task["batches"], "sections": build_p54(task, facts, flags, table, text)})
    for folder in (RUN56, RUN56 / "synthetic"):
        tasks = tasks_of(folder)
        for res in load_jsonl(folder / "results.jsonl"):
            text = accepted_text(res)
            if text is None:
                continue
            task = dict(tasks[res["task_id"]])
            if task["basis"] == "q3b_qualification":
                task.setdefault("mdd", "40")
                j = live[task["mdd"]][task["column"]]
                task.update(q3b_quote=q3b_row_quote(task["mdd"]), q3b_page=str(j.page), q3b_version=j.doc_version)
            facts, flags, _ = compute_spec_facts(task)
            items.append({"part": "3.2.P.5.6", "task_id": task["task_id"], "attribute": task["attribute"],
                          "batch_ids": [], "sections": build_p56(task, facts, flags, text)})
    return items


def docx_ok(rep):
    return not rep["problems"] and rep["numbers"] == rep["placements"] and rep["uncovered"] == 0


def report_text(report, docx_report=None):
    lines = ["== HTML ==", f"numbers {report['numbers']}", f"placements {report['placements']}", f"data-src in html {report['data_src']}",
             f"sections written {report['sections']}", f"uncovered {report['uncovered']}", f"missing {report['missing']}",
             f"rejected sections {len(report['rejected'])}"]
    lines += [f"  {r.part}/{r.task_id}/{r.name}: {r.reason}" for r in report["rejected"]]
    ok = report["numbers"] == report["placements"] == report["data_src"] and report["uncovered"] == 0
    lines.append("RESULT html " + ("numbers == placements" if ok else "MISMATCH"))
    if docx_report is not None:
        d = docx_report
        lines += ["== DOCX (re-read from the saved file) ==", f"numbers {d['numbers']}", f"placements {d['placements']}",
                  f"sections written {d['sections']}", f"uncovered {d['uncovered']}", f"missing {d['missing']}",
                  f"rejected sections {len(d['rejected'])}"]
        lines += [f"  problem: {p}" for p in d["problems"]]
        lines.append("RESULT docx " + ("numbers == placements" if docx_ok(d) else "MISMATCH"))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="folder for P5.html, placements.jsonl, report.txt")
    ap.add_argument("--docx", action="store_true", help="also write P5.docx and re-read the saved file")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    from ectd_engine.render.html import build_document
    items = build_items()
    doc, records, report = build_document(items)
    (out / "P5.html").write_text(doc, encoding="utf-8")
    (out / "placements.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    drep = None
    if args.docx:
        from ectd_engine.render.docx import build_docx, reread
        built = build_docx(items, out / "P5.docx")
        drep = reread(out / "P5.docx", built)
    text = report_text(report, drep)
    (out / "report.txt").write_text(text, encoding="utf-8")
    print(text, end="")
    html_ok = report["numbers"] == report["placements"] == report["data_src"] and not report["rejected"] and not report["uncovered"]
    return 0 if html_ok and (drep is None or docx_ok(drep)) else 1


if __name__ == "__main__":
    sys.exit(main())
