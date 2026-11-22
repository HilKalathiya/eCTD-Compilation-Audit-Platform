"""Puts the P.8 stability facts and the P.5 specification facts into Neo4j (own M23- ids, own node labels) and reads them back as plain text."""
import hashlib
import re
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from ectd_engine.facts.schema import Fact, SourcePointer
from ectd_engine.graph import facts_graph
from ectd_engine.specs import load as spec_load
from ectd_engine.stability import facts as SF

PREFIX = "M23-"                       # every node written here has a fact_id that starts with this; nothing else is touched
LABEL = "In illustrative demonstration data, "
STAB_DOC = "finerenone_stability.csv"
LABELS = {"stability": "StabFact", "spec": "SpecFact"}
_PAGE = re.compile(r"p\.(\d+)$")
_CRT = re.compile(r"^(\d+)-(\d+)C CRT$")

_PUT = {
    "StabFact": """
MERGE (f:StabFact {fact_id: $fact_id})
SET f += $props
MERGE (s:Source {doc_id: $doc_id, doc_version: $doc_version})
MERGE (s)-[r:STATES]->(f)
SET r.locator = $locator
""",
    "SpecFact": """
MERGE (f:SpecFact {fact_id: $fact_id})
SET f += $props
MERGE (s:Source {doc_id: $doc_id, doc_version: $doc_version})
MERGE (s)-[r:STATES]->(f)
SET r.locator = $locator
""",
}
_READ = """
MATCH (f) WHERE (f:StabFact OR f:SpecFact) AND f.fact_id STARTS WITH $prefix
RETURN properties(f) AS p
"""


def stab_id(condition, attribute, month):
    """The graph id of one stability fact."""
    return f"{PREFIX}P8|{condition}|{attribute}|{month}"


def spec_id(attribute):
    """The graph id of one specification fact."""
    return f"{PREFIX}SPEC-LEK-{attribute}"


def _row(fact, family, kind, **extra):
    """One graph row: the 12 contract fields (text only) plus the extra properties 2.3 needs."""
    props = facts_graph.fact_to_props(fact)
    props.update({"family": family, "kind": kind, "attribute": "", "limit_text": "", "limit_kind": "", "page": "",
                  "demo_label": "", "basis": "", "derived": "no"})
    props.update(extra)
    return props


def collect_stability(path=SF.DEFAULT_CSV):
    """{fact_id: row} for every row of the stability CSV (public rows keep their page, DEMO rows keep the label and the page).

    Storage 20 and 25 exist only inside the condition text '20-25C CRT'; they are added as two derived facts (derived = yes)."""
    rows = SF.load_rows(path)
    problems = SF.check_rows(rows)
    if problems:
        raise ValueError("stability data is not clean: " + "; ".join(problems[:5]))
    version = "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
    out = {}
    for r in rows:
        kind, page = SF.source_kind(r["source"]), int(_PAGE.search(r["source"]).group(1))
        fact = Fact(fact_id=stab_id(r["condition"], r["attribute"], r["month"]), value=Decimal(r["value"]),
                    unit=r["unit"], batch=PREFIX + "P8", test=r["attribute"], condition=r["condition"], month=int(r["month"]),
                    source=SourcePointer(STAB_DOC, version, "row=%d" % r["_line"]), lineage="unknown",
                    definition="stability row %d of %s; source text: %s" % (r["_line"], STAB_DOC, r["source"]))
        out[fact.fact_id] = _row(fact, "stability", kind, attribute=r["attribute"], limit_text=r["limit"], page=str(page),
                                 demo_label=LABEL if kind == "demo" else "")
        m = _CRT.match(r["condition"])
        if r["attribute"] == "expiry_period_proposed" and m:
            for name, number in (("storage_low", m.group(1)), ("storage_high", m.group(2))):
                d = Fact(fact_id=stab_id(r["condition"], name, r["month"]), value=Decimal(number), unit="C", batch=PREFIX + "P8",
                         test=name, condition=r["condition"], month=int(r["month"]),
                         source=SourcePointer(STAB_DOC, version, "typed=page=%d" % page), lineage="unknown",
                         definition="storage temperature read from the condition text %r of the proposed-shelf-life row (page %d)" % (r["condition"], page))
                out[d.fact_id] = _row(d, "stability", "public", attribute=name, page=str(page), derived="yes")
    return out


def collect_spec():
    """{fact_id: row} for the five Lek specification limits (declared or Q3B-based, all for the demonstration product)."""
    spec = spec_load.load()
    out = {}
    for r in spec.rows:
        fact = replace(r.fact, fact_id=spec_id(r.attribute), test=r.test, batch=PREFIX + "SPEC")
        out[fact.fact_id] = _row(fact, "spec", "demo", attribute=r.attribute, limit_kind=r.limit_kind, basis=r.basis,
                                 demo_label=LABEL)
    return out


def collect():
    """Every fact 2.3 may use, in the shape the graph holds them."""
    return {**collect_stability(), **collect_spec()}


def put_all(session, facts):
    """Write (or re-write) the facts. Returns how many."""
    for row in facts.values():
        session.run(_PUT[LABELS[row["family"]]], fact_id=row["fact_id"], props=row, doc_id=row["doc_id"],
                    doc_version=row["doc_version"], locator=row["locator"]).consume()
    return len(facts)


def read_all(session, prefix=PREFIX):
    """{fact_id: row} as the graph holds them now (read fresh, nothing cached)."""
    return {rec["p"]["fact_id"]: dict(rec["p"]) for rec in session.run(_READ, prefix=prefix)}
