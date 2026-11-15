"""Planted test: when the database is down or silent, connecting fails fast with a clear error instead of hanging."""
import socket
import time
import unittest

from ectd_engine.db import graph as db_graph
from ectd_engine.db import postgres as db_postgres
from ectd_engine.facts import store
from ectd_engine.graph import facts_graph

LIMIT = 15  # seconds; the connect timeout is 5


def closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def env_for(port):
    return {
        "POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": str(port),
        "APP_DB_USER": "x", "APP_DB_PASSWORD": "x",
        "POSTGRES_USER": "x", "POSTGRES_PASSWORD": "x",
        "NEO4J_URI": f"bolt://127.0.0.1:{port}", "NEO4J_PASSWORD": "x",
    }


class ClosedPort(unittest.TestCase):
    def check(self, fn, service):
        t = time.time()
        with self.assertRaises(store.DatabaseDown) as cm:
            fn()
        self.assertLess(time.time() - t, LIMIT)
        self.assertIn(service, str(cm.exception))
        self.assertIn("docker compose", str(cm.exception))

    def test_postgres_closed_port(self):
        env = env_for(closed_port())
        self.check(lambda: store.connect_app(env), "Postgres")

    def test_neo4j_closed_port(self):
        env = env_for(closed_port())
        self.check(lambda: facts_graph.connect(env), "Neo4j")

    def test_db_postgres_connect_closed_port(self):
        env = env_for(closed_port())
        self.check(lambda: db_postgres.connect(env), "Postgres")

    def test_db_graph_connect_closed_port(self):
        env = env_for(closed_port())
        self.check(lambda: db_graph.connect(env), "Neo4j")


class SilentPort(unittest.TestCase):
    """A port that accepts the connection but never answers: the case that used to hang."""

    def setUp(self):
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(5)
        self.env = env_for(self.srv.getsockname()[1])

    def tearDown(self):
        self.srv.close()

    def test_postgres_silent_port(self):
        t = time.time()
        with self.assertRaises(store.DatabaseDown) as cm:
            store.connect_app(self.env)
        self.assertLess(time.time() - t, LIMIT)
        self.assertIn("Postgres", str(cm.exception))

    def test_neo4j_silent_port(self):
        t = time.time()
        with self.assertRaises(store.DatabaseDown) as cm:
            facts_graph.connect(self.env)
        self.assertLess(time.time() - t, LIMIT)
        self.assertIn("Neo4j", str(cm.exception))

    def test_db_postgres_connect_silent_port(self):
        t = time.time()
        with self.assertRaises(store.DatabaseDown) as cm:
            db_postgres.connect(self.env)
        self.assertLess(time.time() - t, LIMIT)
        self.assertIn("Postgres", str(cm.exception))

    def test_db_graph_connect_silent_port(self):
        t = time.time()
        with self.assertRaises(store.DatabaseDown) as cm:
            db_graph.connect(self.env)
        self.assertLess(time.time() - t, LIMIT)
        self.assertIn("Neo4j", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
