"""Sets up the database: creates the limited ectd_app login and applies the numbered .sql files."""
import hashlib
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


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(conn, path):
    conn.execute("INSERT INTO schema_migrations (filename, sha256) VALUES (%s, %s)", (path.name, _digest(path)))


def migrate(env=None, migrations_dir=None):
    """Apply each .sql file once, in order; a file edited after it ran is a loud error."""
    env = env or load_env()
    files = sorted(Path(migrations_dir or MIGRATIONS).glob("*.sql"))
    conn = postgres.connect(env)
    try:
        ensure_app_role(conn, env)
        first_time = conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0] is None
        legacy = first_time and conn.execute("SELECT to_regclass('facts')").fetchone()[0] is not None
        conn.execute((MIGRATIONS / "005_schema_migrations.sql").read_text(encoding="utf-8"))
        if legacy:  # database from before this table: files 001-004 already ran, only note them
            for path in files:
                if path.name < "005":
                    _record(conn, path)
        conn.commit()
        done = dict(conn.execute("SELECT filename, sha256 FROM schema_migrations").fetchall())
        for path in files:
            if path.name in done:
                if done[path.name] != _digest(path):
                    raise RuntimeError(f"migration edited after it ran: {path.name}")
                continue
            try:
                conn.execute(path.read_text(encoding="utf-8"))
                _record(conn, path)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
    print("migrations applied")
