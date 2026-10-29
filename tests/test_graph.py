"""Tests the graph copy of accepted facts and the drift check, with planted errors and (if the databases are up) live runs."""
import unittest
import uuid

from ectd_engine.gate import gate
from ectd_engine.graph import compare, facts_graph
from tests.test_gate import FakeConn, cand

REGISTRY = {"B1", "B2", "B3"}


def row(fid="F1", **over):
    d = {"fact_id": fid, "value_text": "0.14", "unit": "%", "batch": "B1", "test": "Impurity A",
         "condition": "25C/60%RH", "month": "6", "lineage": "original", "definition": "x",
         "doc_id": "DOC-1", "doc_version": "v1", "locator": "row=12"}
    d.update(over)
    return d


class FakeResult:
    def consume(self):
        pass


class FakeGraph:
    def __init__(self):
        self.calls = []

    def run(self, cypher, **params):
        self.calls.append(params)
        return FakeResult()


class CompareTests(unittest.TestCase):
    def test_equal_stores_have_no_mismatch(self):
        self.assertEqual(compare.compare({"F1": row()}, {"F1": row()}), [])

    def test_value_edited_in_graph_only_is_reported(self):
        m = compare.compare({"F1": row()}, {"F1": row(value_text="0.15")})
        self.assertEqual(m, [{"fact_id": "F1", "problem": "field_differs", "field": "value_text",
                              "postgres": "0.14", "graph": "0.15"}])

    def test_same_number_spelled_differently_is_a_mismatch(self):
        m = compare.compare({"F1": row(value_text="0.140")}, {"F1": row(value_text="0.14")})
        self.assertEqual([x["field"] for x in m], ["value_text"])

    def test_fact_missing_in_graph_is_reported(self):
        self.assertEqual(compare.compare({"F1": row()}, {}), [{"fact_id": "F1", "problem": "missing_in_graph"}])

    def test_fact_missing_in_postgres_is_reported(self):
        self.assertEqual(compare.compare({}, {"F1": row()}), [{"fact_id": "F1", "problem": "missing_in_postgres"}])

    def test_source_or_batch_change_is_reported(self):
        m = compare.compare({"F1": row()}, {"F1": row(locator="row=13", batch="B2")})
        self.assertEqual(sorted(x["field"] for x in m), ["batch", "locator"])


class GateGraphTests(unittest.TestCase):
    def test_accepted_fact_is_written_to_graph(self):
        g = FakeGraph()
        r = gate.submit(cand(), REGISTRY, FakeConn(), graph=g)
        self.assertIsInstance(r, gate.Accepted)
        self.assertEqual(len(g.calls), 1)
        self.assertEqual(g.calls[0]["value_text"], "0.14")
        self.assertIsInstance(g.calls[0]["value_text"], str)

    def test_quarantined_fact_is_not_in_graph(self):
        g = FakeGraph()
        for c in (cand(batch="B99"), cand(unit="mg"), cand(value="1.4"), cand(test="Mystery")):
            self.assertNotIsInstance(gate.submit(c, REGISTRY, FakeConn(), graph=g), gate.Accepted)
        self.assertEqual(g.calls, [])

    def test_converted_value_is_what_the_graph_gets(self):
        g = FakeGraph()
        gate.submit(cand(value="1400", unit="ppm"), REGISTRY, FakeConn(), graph=g)
        self.assertEqual((g.calls[0]["value_text"], g.calls[0]["unit"]), ("0.1400", "%"))

    def test_float_property_is_refused(self):
        with self.assertRaises(TypeError):
            facts_graph.graph.check_props({"value_text": 0.14})


def _live_stores():
    """Return (pg_conn, neo4j_driver) or raise unittest.SkipTest saying which store is down."""
    from ectd_engine.db import graph as db_graph
    from ectd_engine.facts import store
    try:
        pg = store.connect_app()
    except Exception as e:
        raise unittest.SkipTest(f"Postgres is down or not set up ({e!r}); start it with docker compose --profile db up -d")
    try:
        drv = db_graph.connect()
    except Exception as e:
        pg.close()
        raise unittest.SkipTest(f"Neo4j is down or not set up ({e!r}); start it with docker compose --profile graph up -d")
    return pg, drv


class LiveGraphTests(unittest.TestCase):
    P = "T14-"

    @classmethod
    def setUpClass(cls):
        from ectd_engine.db import migrate
        cls.pg, cls.drv = _live_stores()
        migrate.migrate()

    @classmethod
    def tearDownClass(cls):
        from ectd_engine.db import postgres
        with cls.drv.session() as s:
            s.run("MATCH (n) WHERE n.fact_id STARTS WITH $p OR n.doc_id STARTS WITH $p OR n.id STARTS WITH $p "
                  "DETACH DELETE n", p=cls.P).consume()
        cls.drv.close()
        cls.pg.close()
        owner = postgres.connect()
        owner.execute("DELETE FROM facts WHERE fact_id LIKE 'T14-%'")
        owner.commit()
        owner.close()

    def submit_three(self):
        ids = [self.P + uuid.uuid4().hex[:10] for _ in range(3)]
        with self.drv.session() as s:
            for i, f in enumerate(ids):
                r = gate.submit(cand(fact_id=f, value=["0.140", "0.32", "0.05"][i], batch="T14-B1",
                                     source={"doc_id": "T14-DOC", "doc_version": "v1", "locator": f"row={i + 1}"}),
                                {"T14-B1"}, self.pg, graph=s)
                self.assertIsInstance(r, gate.Accepted)
        return ids

    def both(self, s):
        return compare.read_postgres(self.pg, self.P), facts_graph.read_all(s, self.P)

    def test_three_facts_in_both_stores_then_edit_in_graph_is_caught(self):
        ids = self.submit_three()
        with self.drv.session() as s:
            pg_facts, g_facts = self.both(s)
            self.assertEqual(sorted(pg_facts), sorted(ids))
            self.assertEqual(compare.compare(pg_facts, g_facts), [])
            self.assertEqual(g_facts[ids[0]]["value_text"], "0.140")
            s.run("MATCH (f:Fact {fact_id: $f}) SET f.value_text = '0.14'", f=ids[0]).consume()
            m = compare.compare(*self.both(s))
            self.assertEqual([(x["fact_id"], x["field"], x["postgres"], x["graph"]) for x in m],
                             [(ids[0], "value_text", "0.140", "0.14")])
            s.run("MATCH (f:Fact {fact_id: $f}) DETACH DELETE f", f=ids[1]).consume()
            m = compare.compare(*self.both(s))
            self.assertIn({"fact_id": ids[1], "problem": "missing_in_graph"}, m)


if __name__ == "__main__":
    unittest.main()
