"""Reads the tablet strengths from saved Kerendia DailyMed label files (SPL XML, two versions) and sends each through the gate with an xml path."""
import argparse
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ectd_engine.gate import gate
from ectd_engine.loaders.fda_pdf import _Dry

ROOT = Path(__file__).resolve().parents[2]
NS = "{urn:hl7-org:v3}"
FILES = (  # the earliest 2021 label and the July 2025 label; sha256 in data/public/SOURCES.md
    "data/public/kerendia/kerendia_spl_v1.xml",
    "data/public/kerendia/kerendia_spl_v12.xml",
)
CONDITION = "label"
BATCH = "n/a"
DEFINITION = "Strength of the active ingredient per tablet, as listed in the DailyMed label (SPL) product data"


def _local(tag):
    return tag.replace(NS, "")


def xml_path(root, target):
    """Return /document/a[1]/b[2]/... : each step is the tag plus its position among same-named siblings."""
    steps = []
    node = target
    parents = {c: p for p in root.iter() for c in p}
    while node is not root:
        parent = parents[node]
        same = [c for c in parent if c.tag == node.tag]
        steps.append(f"{_local(node.tag)}[{same.index(node) + 1}]")
        node = parent
    return "/" + "/".join([_local(root.tag)] + steps[::-1])


def resolve(root, path):
    """Walk an xml_path back to the element it names (inverse of xml_path); None if it does not exist."""
    steps = path.lstrip("/").split("/")
    if _local(root.tag) != steps[0]:
        return None
    node = root
    for step in steps[1:]:
        tag, _, idx = step.partition("[")
        kids = [c for c in node if _local(c.tag) == tag]
        i = int(idx.rstrip("]")) - 1
        if i >= len(kids):
            return None
        node = kids[i]
    return node


def build(files=FILES, base=ROOT):
    """Return one candidate per listed strength per file; the number is copied from the XML attribute, never typed."""
    cands = []
    for rel in files:
        root = ET.parse(Path(base) / rel).getroot()
        set_id = root.find(f"{NS}setId").get("root")
        version = root.find(f"{NS}versionNumber").get("value")
        n = 0
        for ing in root.iter(f"{NS}ingredient"):
            if ing.get("classCode") != "ACTIB":
                continue
            num = ing.find(f"{NS}quantity/{NS}numerator")
            if num is None:
                continue
            n += 1
            try:
                value = str(Decimal(num.get("value")))
            except InvalidOperation as e:
                raise ValueError(f"{rel}: strength {num.get('value')!r} is not a number") from e
            cands.append({"fact_id": f"KER-SPL-v{version}-STRENGTH-{n}", "value": value, "unit": num.get("unit"),
                          "batch": BATCH, "test": "Strength", "condition": CONDITION, "month": None,
                          "source": {"doc_id": set_id, "doc_version": version, "locator": "xml=" + xml_path(root, num)},
                          "lineage": "original", "definition": DEFINITION})
    return cands


def load(conn, graph=None, files=FILES, base=ROOT, rules=None):
    """Submit every candidate through gate.submit; return [(candidate, result)]."""
    rules = rules or gate.load_rules()
    return [(c, gate.submit(c, {BATCH}, conn, rules, graph)) for c in build(files, base)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print each fact; nothing is stored")
    args = ap.parse_args(argv)
    if not args.dry_run:
        ap.error("only --dry-run is allowed for now (no live load yet)")
    dry = _Dry()
    for c, r in load(dry, dry):
        status = "accepted" if isinstance(r, gate.Accepted) else f"quarantined {r.reason_code}"
        s = c["source"]
        print(f"v{s['doc_version']} {c['fact_id']}: {c['value']} {c['unit']} [{c['test']}] {s['locator']} -> {status}")


if __name__ == "__main__":
    main()
