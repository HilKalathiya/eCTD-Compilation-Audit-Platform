"""Live test of the A0 checkpoint: the demo runs on real Postgres and Neo4j, and a planted graph edit makes proof 5 fail."""
import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path

from ectd_engine import demo_facts

ROOT = Path(__file__).resolve().parents[1]


def require_databases():
    """FAIL (not skip) with a plain message when Postgres or Neo4j is down."""
    from ectd_engine.db import graph, postgres
    try:
        postgres.connect().close()
        graph.connect().close()
    except Exception as e:
        raise AssertionError(f"{demo_facts.DOWN} ({e!r})")


class DemoFactsLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_databases()

    @classmethod
    def tearDownClass(cls):
        demo_facts.clean()  # demo rows use newer locator forms that make a later migrate fail, so leave none behind

    def test_demo_command_exits_0_with_5_proof_lines(self):
        r = subprocess.run([sys.executable, "-m", "ectd_engine.demo_facts"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        proofs = [ln for ln in r.stdout.splitlines() if ln.startswith("PROOF ")]
        self.assertEqual(len(proofs), 5, r.stdout)
        self.assertTrue(all(ln.startswith(f"PROOF {i} OK") for i, ln in enumerate(proofs, start=1)), r.stdout)

    def test_planted_edit_in_graph_fails_proof_5_and_exit_1(self):
        def edit_one_node(session):
            session.run("MATCH (f:Fact) WHERE f.fact_id STARTS WITH $p AND f.fact_id ENDS WITH '-dissolution_av' "
                        "WITH f LIMIT 1 SET f.value_text = '99.99'", p=demo_facts.PREFIX + "LEK-").consume()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = demo_facts.main([], tamper=edit_one_node)
        lines = buf.getvalue().splitlines()
        self.assertEqual(code, 1, buf.getvalue())
        self.assertTrue(any(ln.startswith("PROOF 5 FAIL") for ln in lines), buf.getvalue())
        self.assertEqual(sum(ln.startswith("PROOF ") and " OK" in ln for ln in lines), 4, buf.getvalue())

    def test_databases_down_gives_clear_message_and_exit_1(self):
        out = []
        from unittest import mock
        with mock.patch("ectd_engine.demo_facts.postgres.connect", side_effect=OSError("down")):
            code = demo_facts.run(out=out.append)
        self.assertEqual(code, 1)
        self.assertIn("start Docker", out[0])


if __name__ == "__main__":
    unittest.main()
