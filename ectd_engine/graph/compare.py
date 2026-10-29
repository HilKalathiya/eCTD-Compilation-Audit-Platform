"""Drift check: lists every fact that is missing from, or differs between, Postgres and the graph."""
from ectd_engine.graph.facts_graph import FIELDS

_SQL = ("SELECT fact_id, value_text, unit, batch, test, condition, month, lineage, definition, "
        "doc_id, doc_version, locator FROM facts WHERE fact_id LIKE %s")


def read_postgres(conn, prefix=""):
    """Return {fact_id: {field: text}} from Postgres, in the same shape as facts_graph.read_all."""
    rows = conn.execute(_SQL, (prefix.replace("%", r"\%").replace("_", r"\_") + "%",)).fetchall()
    conn.commit()
    out = {}
    for row in rows:
        d = dict(zip(FIELDS, row))
        d["month"] = "" if d["month"] is None else str(d["month"])
        out[d["fact_id"]] = d
    return out


def compare(pg_facts, graph_facts):
    """Return a list of mismatches; [] means both stores hold the same facts (values compared as text)."""
    found = []
    for fid in sorted(set(pg_facts) | set(graph_facts)):
        if fid not in graph_facts:
            found.append({"fact_id": fid, "problem": "missing_in_graph"})
        elif fid not in pg_facts:
            found.append({"fact_id": fid, "problem": "missing_in_postgres"})
        else:
            for field in FIELDS:
                a, b = pg_facts[fid].get(field), graph_facts[fid].get(field)
                if a != b:
                    found.append({"fact_id": fid, "problem": "field_differs", "field": field,
                                  "postgres": a, "graph": b})
    return found
