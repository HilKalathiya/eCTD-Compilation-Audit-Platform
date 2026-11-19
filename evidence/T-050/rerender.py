"""Re-renders every accepted T-048 paragraph with the T-050 renderer (no model), writes rendered.md and counts hits for every prose rule."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def main(dest):
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("rerender_t049", ROOT / "evidence" / "T-049" / "rerender.py")
    rr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rr)
    from tests.test_mutation_spec import live_data
    from tests.test_spec_writer import SpecWriterTests as T
    items = rr.rerender_all(live_data())
    lines = [f"# T-050 re-rendered paragraphs ({len(items)})", ""]
    for tid, _, para in items:
        lines += [f"## {tid}", para, ""]
    Path(dest).write_text("\n".join(lines), encoding="utf-8")
    rules = {"old rules (batches of, resting on declared, set declared, batches results, U+FFFD, mojibake, case)": T.OLD_PROSE, **T.NEW_PROSE}
    print(f"{len(items)} paragraphs -> {dest}")
    for name, rx in rules.items():
        hits = sum(1 for _, _, para in items if rx.search(para))
        print(f"  {hits:3d} hits  {name}")
    for needle in ("resting", "relying", "set declared"):
        print(f"  {sum(needle in p for _, _, p in items):3d} paragraphs contain {needle!r}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).with_name("rendered.md")))
