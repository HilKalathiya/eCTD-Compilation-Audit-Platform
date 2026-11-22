"""Builds Module 2.3 (2.3.P.5 and 2.3.P.8) from the graph facts into a NEW run folder; no model, no 3.2 file is touched.

    python tools/render_summary.py --out evidence/T-068/run1 --load-graph --docx --reread
    (--load-graph writes the M23- facts into Neo4j first; an existing --out folder is refused)
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ectd_engine.graph import facts_graph, summary_graph  # noqa: E402
from ectd_engine.summary import build  # noqa: E402


def reread_docx(folder):
    """Run tools/reread_export.reread on the saved 2.3 .docx (no plan: that plan is the 3.2.P.5 one). Writes reread.txt and flags.csv."""
    from tools import reread_export
    rep = reread_export.reread(folder / "M23.docx", reread_export.read_placements(folder / "placements.jsonl"), set(), None)
    with open(folder / "reread_flags.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["unit", "section", "flag", "text"])
        w.writeheader()
        w.writerows(rep["flags"])
    lines = ["== reread_export.reread on M23.docx (plan=None) ==", f"text units {rep['paragraphs']}", f"numbers {rep['numbers']}",
             f"placements {rep['placements']}", f"uncovered {rep['uncovered']}", f"reviewer flags {len(rep['flags'])} (see reread_flags.csv)"]
    lines += [f"  problem: {p}" for p in rep["problems"]]
    lines.append("RESULT docx numbers == placements" if rep["numbers"] == rep["placements"] and not rep["problems"] else "RESULT see problems")
    (folder / "reread.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="a NEW run folder (an existing one is refused)")
    ap.add_argument("--load-graph", action="store_true", help="write the M23- facts into Neo4j before reading them back")
    ap.add_argument("--docx", action="store_true", help="also write M23.docx")
    ap.add_argument("--reread", action="store_true", help="run tools/reread_export.reread on the saved .docx (needs --docx)")
    args = ap.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        print(f"{out} already exists; use a new run folder (runs are never overwritten)")
        return 2
    driver = facts_graph.connect()
    try:
        with driver.session() as session:
            if args.load_graph:
                print("facts written to the graph:", summary_graph.put_all(session, summary_graph.collect()))
            facts = summary_graph.read_all(session)
    finally:
        driver.close()
    report = build.write_run(out, facts, docx=args.docx)
    print((out / "report.txt").read_text(encoding="utf-8"), end="")
    if args.reread and args.docx:
        print("\n".join(reread_docx(out)))
    return 1 if report["rejected"] or report["uncovered"] or report["docx_problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
