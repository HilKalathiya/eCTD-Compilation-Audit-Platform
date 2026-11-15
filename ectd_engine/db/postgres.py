"""Connects to Postgres, turns on pgvector, and finds columns that could round numbers."""
import psycopg

from ectd_engine.db.config import load_env
from ectd_engine.facts.store import CONNECT_TIMEOUT, DatabaseDown

FLOAT_TYPES = ("real", "double precision")


def connect(env=None):
    """Connect as the admin login; give up after 5 s with a clear DatabaseDown error."""
    env = env or load_env()
    host = env.get("POSTGRES_HOST", "localhost")
    port = int(env.get("POSTGRES_PORT", "5432"))
    try:
        conn = psycopg.connect(
            host=host,
            port=port,
            user=env["POSTGRES_USER"],
            password=env["POSTGRES_PASSWORD"],
            dbname=env.get("POSTGRES_DB", "ectd"),
            connect_timeout=CONNECT_TIMEOUT,
        )
    except psycopg.OperationalError as e:
        raise DatabaseDown(
            f"Postgres is not reachable at {host}:{port} (waited {CONNECT_TIMEOUT}s). "
            f"Start it with: docker compose --profile db up -d. Detail: {str(e).strip()[:200]}"
        ) from e
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    return conn


def float_columns(conn):
    """List (table, column, type) for every real/double precision column in schema public."""
    rows = conn.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND data_type = ANY(%s) "
        "ORDER BY table_name, column_name",
        (list(FLOAT_TYPES),),
    ).fetchall()
    return [tuple(r) for r in rows]
