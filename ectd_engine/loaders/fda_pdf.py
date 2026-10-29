"""Finds listed numbers in the Kerendia FDA chemistry review PDF and sends each one through the gate with page + word box."""
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import fitz  # PyMuPDF

from ectd_engine.gate import gate

ROOT = Path(__file__).resolve().parents[2]
TARGETS_PATH = Path(__file__).resolve().parent / "kerendia_targets.json"
CONDITION = "label"
BATCH = "n/a"


class NotFound(ValueError):
    """The expected word is not on the named page (or not clearly one place)."""


def no_text_pages(doc):
    """Return page numbers (1-based) with no text layer; those need C1.7b blind double typing."""
    return [i for i, page in enumerate(doc, start=1) if not page.get_text("words")]


def find_word(doc, target):
    """Return (x0, y0, x1, y1) of the one word equal to target['expected'] on target['page'] whose line holds every label word."""
    n = target["page"]
    if not 1 <= n <= len(doc):
        raise NotFound(f"{target['key']}: not found at page {n} (document has {len(doc)} pages)")
    lines = {}
    for w in doc[n - 1].get_text("words"):
        lines.setdefault((w[5], w[6]), []).append(w)
    hits = []
    for words in lines.values():
        texts = [w[4] for w in words]
        if all(lbl in texts for lbl in target["label"]):
            hits += [w for w in words if w[4] == target["expected"]]
    if not hits:
        raise NotFound(f"{target['key']}: {target['expected']!r} with label {target['label']} not found at page {n}")
    if len(hits) > 1:
        raise NotFound(f"{target['key']}: {target['expected']!r} with label {target['label']} found {len(hits)} times at page {n}; make the label more specific")
    return hits[0][:4]


def candidate(target, box, cfg):
    """Build the fact candidate; the value is read from the word text found, never typed twice."""
    try:
        value = str(Decimal(target["expected"]))
    except InvalidOperation as e:
        raise ValueError(f"{target['key']}: {target['expected']!r} is not a number") from e
    x0, y0, x1, y1 = box
    return {"fact_id": f"KER-CHEMR-{target['key']}", "value": value, "unit": target["unit"], "batch": BATCH,
            "test": target["test"], "condition": CONDITION, "month": None,
            "source": {"doc_id": cfg["doc_id"], "doc_version": cfg["doc_version"],
                       "locator": f"page={target['page']};box={x0:.2f},{y0:.2f},{x1:.2f},{y1:.2f}"},
            "lineage": "original", "definition": target["definition"]}


def build(cfg=None, doc=None):
    """Return the list of candidates for every target; a target not found stops the run loudly."""
    cfg = cfg or json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
    doc = doc or fitz.open(ROOT / cfg["pdf"])
    return [candidate(t, find_word(doc, t), cfg) for t in cfg["targets"]]


def load(conn, graph=None, cfg=None, doc=None, rules=None):
    """Submit every target through gate.submit; return [(candidate, result)]."""
    cands = build(cfg, doc)
    registry = {BATCH}
    rules = rules or gate.load_rules()
    return [(c, gate.submit(c, registry, conn, rules, graph)) for c in cands]


class _Dry:
    """Stand-in for the database and the graph: records calls, stores nothing."""

    def execute(self, sql, params=()):
        return self

    def commit(self):
        pass

    def rollback(self):
        pass

    def run(self, *a, **k):
        return self

    def consume(self):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print each fact; nothing is stored")
    args = ap.parse_args(argv)
    if not args.dry_run:
        ap.error("only --dry-run is allowed for now (no live load yet)")
    cfg = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
    doc = fitz.open(ROOT / cfg["pdf"])
    blank = no_text_pages(doc)
    print(f"pages without text layer: {len(blank)} {blank}")
    dry = _Dry()
    for c, r in load(dry, dry, cfg, doc):
        status = "accepted" if isinstance(r, gate.Accepted) else f"quarantined {r.reason_code}"
        print(f"{c['fact_id']}: {c['value']} {c['unit']} [{c['test']}] {c['source']['locator']} -> {status}")


if __name__ == "__main__":
    main()
