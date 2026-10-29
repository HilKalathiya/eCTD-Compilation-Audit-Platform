"""Writes accepted facts into Neo4j (only the gate calls this) and reads them back as plain text."""
from ectd_engine.db import graph

FIELDS = ("fact_id", "value_text", "unit", "batch", "test", "condition", "month",
          "lineage", "definition", "doc_id", "doc_version", "locator")

_PUT = """
MERGE (f:Fact {fact_id: $fact_id})
SET f.value_text = $value_text, f.unit = $unit, f.test = $test, f.condition = $condition,
    f.month = $month, f.lineage = $lineage, f.definition = $definition
MERGE (b:Batch {id: $batch})
MERGE (b)-[:HAS_FACT]->(f)
MERGE (s:Source {doc_id: $doc_id, doc_version: $doc_version})
MERGE (s)-[r:STATES]->(f)
SET r.locator = $locator
"""

_READ = """
MATCH (b:Batch)-[:HAS_FACT]->(f:Fact)<-[r:STATES]-(s:Source)
WHERE $prefix = '' OR f.fact_id STARTS WITH $prefix
RETURN f.fact_id AS fact_id, f.value_text AS value_text, f.unit AS unit, b.id AS batch,
       f.test AS test, f.condition AS condition, f.month AS month, f.lineage AS lineage,
       f.definition AS definition, s.doc_id AS doc_id, s.doc_version AS doc_version, r.locator AS locator
"""


def fact_to_props(fact):
    """Every field of the fact as text; the number is kept as its exact text, never a float."""
    s = fact.source
    props = {"fact_id": fact.fact_id, "value_text": str(fact.value), "unit": fact.unit, "batch": fact.batch,
             "test": fact.test, "condition": fact.condition,
             "month": "" if fact.month is None else str(fact.month), "lineage": fact.lineage,
             "definition": fact.definition, "doc_id": s.doc_id, "doc_version": s.doc_version, "locator": s.locator}
    graph.check_props(props)
    return props


def put_fact(session, fact):
    """Write (or re-write) one fact with its batch and source links."""
    session.run(_PUT, **fact_to_props(fact)).consume()


def read_all(session, prefix=""):
    """Return {fact_id: {field: text}} for the facts in the graph (optionally only ids starting with prefix)."""
    out = {}
    for rec in session.run(_READ, prefix=prefix):
        out[rec["fact_id"]] = {k: rec[k] for k in FIELDS}
    return out
