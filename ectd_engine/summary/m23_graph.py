"""Where the 2.3 writer gets its numbers: one graph interface with a Neo4j reader (real task) and an in-memory SYNTHETIC adapter (test tasks), plus the derived facts.

Both readers give {fact_id: row} in the same shape, so the same render path runs for both. The in-memory adapter is labelled SYNTHETIC, can never be
written to Neo4j, and loads only a file made for a synthetic task. Derived facts (lowest, highest, outside-limit count, dissolution time point)
are worked out here from the stored rows, with Decimal, when they are needed; they are never typed.
"""
import json
import re
from decimal import Decimal
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import plan as P

_RANGE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$")
_NMT = re.compile(r"^\s*NMT\s+(\d+(?:\.\d+)?)\s*$")
_NLT = re.compile(r"^\s*NLT\s+(\d+(?:\.\d+)?)\s*$")
_TIMEPOINT = re.compile(r"\((\d+) min\)")


class Neo4jGraph:
    """The real graph: reads the M23- facts from Neo4j now, with the project's own query (summary_graph.read_all)."""
    namespace = "NEO4J"

    def rows(self):
        from ectd_engine.graph import facts_graph
        driver = facts_graph.connect()
        try:
            with driver.session() as session:
                return G.read_all(session)
        finally:
            driver.close()


class MemoryGraph:
    """An in-memory stand-in with the same interface, for SYNTHETIC test tasks only. It has no write path and never opens a database."""
    namespace = "SYNTHETIC"

    def __init__(self, rows):
        bad = [k for k, r in rows.items() if r.get("namespace") != "SYNTHETIC" or not k.startswith(G.PREFIX)]
        if bad:
            raise ValueError("not a synthetic graph: these rows are not labelled SYNTHETIC: " + ", ".join(bad[:3]))
        self._rows = {k: dict(r) for k, r in rows.items()}

    def rows(self):
        return {k: dict(r) for k, r in self._rows.items()}


def load_synthetic(path):
    """A MemoryGraph from a synthetic graph file ({"namespace": "SYNTHETIC", "rows": {...}})."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("namespace") != "SYNTHETIC":
        raise ValueError(f"{path} is not labelled SYNTHETIC")
    return MemoryGraph(data["rows"])


def parse_limit(text):
    """'95.0-105.0' -> (95.0, 105.0); 'NMT 0.50' -> (None, 0.50); 'NLT 80' -> (80, None) as Decimal; anything else -> None."""
    m = _RANGE.match(text or "")
    if m:
        return Decimal(m.group(1)), Decimal(m.group(2))
    m = _NMT.match(text or "")
    if m:
        return None, Decimal(m.group(1))
    m = _NLT.match(text or "")
    if m:
        return Decimal(m.group(1)), None
    return None


def outside(value_text, limit_text):
    """True when the stored result breaks its limit (Decimal comparison); a result with no readable limit is NOT counted outside."""
    lim = parse_limit(limit_text)
    if lim is None:
        return False
    v, (lo, hi) = Decimal(value_text), lim
    return (lo is not None and v < lo) or (hi is not None and v > hi)


def group_rows(rows, cond, attr):
    return [r for r in rows.values() if r["family"] == "stability" and r["kind"] == "demo" and r["condition"] == cond and r["attribute"] == attr]


def stats(rows, cond, attr):
    """The derived facts of one condition x attribute: {"low": row, "high": row, "outside": int, "n": int, "timepoint": row | None}.

    low / high are the stored rows with the id of the statistic; outside_limit_count is counted from the stored values and limits."""
    grp = group_rows(rows, cond, attr)
    if not grp:
        raise KeyError(f"no stored results for {cond} | {attr}")
    lo = min(grp, key=lambda r: Decimal(r["value_text"]))
    hi = max(grp, key=lambda r: Decimal(r["value_text"]))
    tp = _TIMEPOINT.search(attr)
    point = None
    if tp:
        point = dict(lo, fact_id=P.stat_id(cond, attr, "timepoint"), value_text=tp.group(1), unit="min", limit_text="")
    return {"low": dict(lo, fact_id=P.stat_id(cond, attr, "min")), "high": dict(hi, fact_id=P.stat_id(cond, attr, "max")),
            "outside": sum(1 for r in grp if outside(r["value_text"], r.get("limit_text", ""))), "n": len(grp), "timepoint": point}


def fact(rows, fact_id):
    """A stored row or a derived one by id. Raises KeyError when the graph does not hold it."""
    if fact_id.startswith(G.PREFIX + "STAT|"):
        cond, attr, which = fact_id[len(G.PREFIX + "STAT|"):].split("|")
        s = stats(rows, cond, attr)
        got = {"min": s["low"], "max": s["high"], "timepoint": s["timepoint"]}.get(which)
        if got is None:
            raise KeyError(fact_id)
        return got
    return rows[fact_id]
