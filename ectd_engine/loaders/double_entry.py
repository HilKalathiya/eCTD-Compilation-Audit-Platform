"""Asks a person to type a number twice, blind, and only makes a fact candidate if both typings match."""
import getpass
import json
import sys
from decimal import Decimal, InvalidOperation

from ectd_engine.loaders import fda_pdf


class Refused(ValueError):
    """The typed values are blank, not numbers, or do not match; no candidate is made."""


def _number(text, which):
    if text is None or not text.strip():
        raise Refused(f"{which} typing is blank")
    try:
        value = Decimal(text.strip())
    except InvalidOperation as e:
        raise Refused(f"{which} typing {text.strip()!r} is not a number") from e
    if not value.is_finite():
        raise Refused(f"{which} typing {text.strip()!r} is not a number")
    return value


def enter_twice(target, cfg, first, second):
    """Return a candidate if the two typings match as numbers; `first` and `second` are zero-argument functions that return the typed text."""
    a = _number(first(), "first")
    b = _number(second(), "second")
    if a != b:
        raise Refused(f"{target['key']}: the two typings do not match; nothing accepted")
    cand = fda_pdf.candidate({**target, "expected": str(a)}, (0.0, 0.0, 0.0, 0.0), cfg)
    cand["definition"] = f"{target['definition']} (typed twice by hand; word box not located)"
    return cand


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.exit("usage: python -m ectd_engine.loaders.double_entry <fact_key>")
    cfg = json.loads(fda_pdf.TARGETS_PATH.read_text(encoding="utf-8"))
    target = next((t for t in cfg["targets"] if t["key"] == argv[0]), None)
    if target is None:
        sys.exit(f"unknown fact_key {argv[0]!r}; known: {', '.join(t['key'] for t in cfg['targets'])}")
    print(f"Type the value of {target['test']} ({target['unit']}), page {target['page']}.")
    try:
        # getpass hides what is typed, so the second prompt can never show the first value
        cand = enter_twice(target, cfg, lambda: getpass.getpass("First typing: "),
                           lambda: getpass.getpass("Second typing (do not look at the first): "))
    except Refused as e:
        print(f"REFUSED: {e}")
        sys.exit(1)
    print(json.dumps(cand, indent=2))


if __name__ == "__main__":
    main()
