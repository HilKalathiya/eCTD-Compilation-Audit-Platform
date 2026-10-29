"""Live checks (containers must be up) that Postgres and Neo4j keep numbers exact."""
import unittest
import uuid
from decimal import Decimal

from ectd_engine.db import graph, postgres


class PostgresLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = postgres.connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.table = "t_" + uuid.uuid4().hex[:8]

    def tearDown(self):
        self.conn.rollback()
        self.conn.execute(f"DROP TABLE IF EXISTS {self.table}")
        self.conn.commit()

    def test_numeric_roundtrip_keeps_trailing_zero(self):
        self.conn.execute(f"CREATE TABLE {self.table} (v NUMERIC(10,3))")
        self.conn.execute(f"INSERT INTO {self.table} VALUES (%s)", (Decimal("0.140"),))
        got = self.conn.execute(f"SELECT v FROM {self.table}").fetchone()[0]
        self.assertEqual(str(got), "0.140")

    def test_pgvector_roundtrip(self):
        self.conn.execute(f"CREATE TABLE {self.table} (v vector(3))")
        self.conn.execute(f"INSERT INTO {self.table} VALUES ('[1,2,3]')")
        got = self.conn.execute(f"SELECT v::text FROM {self.table}").fetchone()[0]
        self.assertEqual(got, "[1,2,3]")

    def test_planted_double_column_is_found(self):
        self.conn.execute(f"CREATE TABLE {self.table} (bad DOUBLE PRECISION, ok NUMERIC(5,2))")
        self.conn.commit()
        found = postgres.float_columns(self.conn)
        self.assertIn((self.table, "bad", "double precision"), found)
        self.assertNotIn(self.table, [t for t, c, _ in found if c == "ok"])

    def test_clean_table_has_no_float_columns(self):
        self.conn.execute(f"CREATE TABLE {self.table} (ok NUMERIC(5,2))")
        self.conn.commit()
        self.assertNotIn(self.table, [t for t, _, _ in postgres.float_columns(self.conn)])


class GraphLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = graph.connect()

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def test_decimal_string_roundtrip_in_node(self):
        key = uuid.uuid4().hex
        props = {"key": key, "value": str(Decimal("0.140"))}
        graph.check_props(props)
        with self.driver.session() as s:
            s.run("CREATE (n:T005Test $p)", p=props).consume()
            got = s.run("MATCH (n:T005Test {key: $k}) RETURN n.value AS v", k=key).single()["v"]
            s.run("MATCH (n:T005Test {key: $k}) DELETE n", k=key).consume()
        self.assertEqual(got, "0.140")

    def test_planted_float_property_raises(self):
        with self.assertRaises(TypeError):
            graph.check_props({"value": 0.14})
        with self.assertRaises(TypeError):
            graph.check_props({"values": [Decimal("1"), 0.14]})

    def test_decimal_and_str_pass(self):
        graph.check_props({"a": "0.140", "b": 3})


if __name__ == "__main__":
    unittest.main()
