"""Connects to Neo4j and refuses float properties (numbers are stored as Decimal strings)."""
from neo4j import GraphDatabase

from ectd_engine.db.config import load_env


def connect(env=None):
    env = env or load_env()
    driver = GraphDatabase.driver(
        env.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(env.get("NEO4J_USER", "neo4j"), env["NEO4J_PASSWORD"]),
    )
    driver.verify_connectivity()
    return driver


def check_props(props):
    """Raise TypeError if any property value is a Python float (also inside lists)."""
    for key, value in props.items():
        items = value if isinstance(value, (list, tuple)) else [value]
        for item in items:
            if isinstance(item, float):
                raise TypeError(f"property {key!r} is a float; store Decimal as str")
