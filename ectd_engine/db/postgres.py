"""Connects to Postgres, turns on pgvector, and finds columns that could round numbers."""
import psycopg

from ectd_engine.db.config import load_env

FLOAT_TYPES = ("real", "double precision")


def connect(env=None):
    env = env or load_env()
    conn = psycopg.connect(
        host=env.get("POSTGRES_HOST", "localhost"),
        port=int(env.get("POSTGRES_PORT", "5432")),
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        dbname=env.get("POSTGRES_DB", "ectd"),
    )
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
