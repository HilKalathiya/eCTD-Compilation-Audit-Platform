"""Live test: database migrations run once each, and an edited migration is refused."""
import shutil
import tempfile
import unittest
from pathlib import Path

from ectd_engine.db import migrate, postgres


def require_database():
    """FAIL (not skip) with a plain message when Postgres is down."""
    try:
        postgres.connect().close()
    except Exception as e:
        raise AssertionError(f"Postgres is not reachable ({e!r}); start Docker") from e


class MigrateTests(unittest.TestCase):
    def setUp(self):
        require_database()

    def applied(self):
        conn = postgres.connect()
        try:
            return conn.execute("SELECT filename, applied_at FROM schema_migrations ORDER BY filename").fetchall()
        finally:
            conn.close()

    def test_second_run_is_a_noop(self):
        migrate.migrate()
        before = self.applied()
        migrate.migrate()
        self.assertEqual(before, self.applied())
        self.assertGreaterEqual(len(before), 5)

    def test_rerun_with_xml_fact_present(self):
        from ectd_engine import demo_facts
        self.assertEqual(demo_facts.run(out=lambda *_: None), 0)  # leaves xml=/typed= label facts stored
        migrate.migrate()

    def test_planted_edited_migration_is_refused(self):
        migrate.migrate()
        tmp = Path(tempfile.mkdtemp())
        try:
            for f in migrate.MIGRATIONS.glob("*.sql"):
                shutil.copy(f, tmp / f.name)
            first = tmp / "001_facts.sql"
            first.write_text(first.read_text(encoding="utf-8") + "\n-- edited\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "migration edited after it ran"):
                migrate.migrate(migrations_dir=tmp)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
