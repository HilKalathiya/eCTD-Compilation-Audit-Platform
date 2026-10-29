"""Sets up the database: creates the limited ectd_app login and applies the numbered .sql files."""
from pathlib import Path

from psycopg import sql

from ectd_engine.db import postgres
from ectd_engine.db.config import load_env

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def ensure_app_role(conn, env):
    """Create the ectd_app login (or reset its password); it gets no table rights here."""
    name, password = env["APP_DB_USER"], env["APP_DB_PASSWORD"]
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,)).fetchone()
    verb = "ALTER" if exists else "CREATE"
    conn.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
        sql.Identifier(name), sql.Literal(password)))
    conn.commit()


def migrate(env=None):
    env = env or load_env()
    conn = postgres.connect(env)
    try:
        ensure_app_role(conn, env)
        for path in sorted(MIGRATIONS.glob("*.sql")):
            conn.execute(path.read_text(encoding="utf-8"))
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
    print("migrations applied")
