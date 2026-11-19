"""Re-renders every accepted T-048 paragraph (no model), runs the shared prose rules and the loop's re-read on each, writes rendered.md."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def main(dest):
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("rerender_t049", ROOT / "evidence" / "T-049" / "rerender.py")
    rr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rr)
    from ectd_engine.validator.spec import verify_render
    from ectd_engine.writer.spec_prose import PROSE_RULES, prose_problems
    from tests.test_mutation_spec import live_data
    items = rr.rerender_all(live_data())
    lines = [f"# T-051 re-rendered paragraphs ({len(items)})", ""]
    rejects = []
    for tid, task, para in items:
        lines += [f"## {tid}", para, ""]
        reasons = ["prose:" + n for n in prose_problems(para)] + ["re-read:" + p for p in verify_render(para, task)]
        if reasons:
            rejects.append((tid, reasons))
    Path(dest).write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(items)} paragraphs -> {dest}")
    print(f"{len(rejects)} rejects by the prose gate or the re-read of {len(items)}")
    for tid, reasons in rejects:
        print("  ", tid, reasons)
    for name, rx in PROSE_RULES.items():
        print(f"  {sum(1 for _, _, p in items if rx.search(p)):3d} hits  {name}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).with_name("rendered.md")))
