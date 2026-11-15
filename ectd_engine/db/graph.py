"""Connects to Neo4j and refuses float properties (numbers are stored as Decimal strings)."""
from neo4j import GraphDatabase

from ectd_engine.db.config import load_env
from ectd_engine.facts.store import CONNECT_TIMEOUT, DatabaseDown


def connect(env=None):
    """Open Neo4j; give up after 5 s with a clear DatabaseDown error."""
    env = env or load_env()
    uri = env.get("NEO4J_URI", "bolt://localhost:7687")
    driver = GraphDatabase.driver(
        uri,
        auth=(env.get("NEO4J_USER", "neo4j"), env["NEO4J_PASSWORD"]),
        connection_timeout=CONNECT_TIMEOUT,
        connection_acquisition_timeout=CONNECT_TIMEOUT,
        max_transaction_retry_time=CONNECT_TIMEOUT,
    )
    try:
        driver.verify_connectivity()
    except Exception as e:
        driver.close()
        raise DatabaseDown(
            f"Neo4j is not reachable at {uri} (waited {CONNECT_TIMEOUT}s). "
            f"Start it with: docker compose --profile graph up -d. Detail: {str(e).strip()[:200]}"
        ) from e
    return driver


def check_props(props):
    """Raise TypeError if any property value is a Python float (also inside lists)."""
    for key, value in props.items():
        items = value if isinstance(value, (list, tuple)) else [value]
        for item in items:
            if isinstance(item, float):
                raise TypeError(f"property {key!r} is a float; store Decimal as str")
