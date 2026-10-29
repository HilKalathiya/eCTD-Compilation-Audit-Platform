"""Tests the Lek loader with a fake database and graph: counts, planted part>total, bad header, bad cell."""
import json
import tempfile
import unittest
from pathlib import Path

from ectd_engine.gate import gate
from ectd_engine.loaders import lek

HEADER = "batch;dissolution_av;resodual_solvent;impurities_total;impurity_o;impurity_l"


class FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self

    def commit(self):
        pass

    def rollback(self):
        pass

    def kinds(self):
        return [("put" if "gate_insert_fact" in s else "quarantine") for s, _ in self.calls]


class FakeGraph:
    def __init__(self):
        self.runs = 0

    def run(self, *a, **k):
        self.runs += 1
        return self

    def consume(self):
        pass


def load_text(text):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "lab.csv"
        p.write_text(text, encoding="utf-8")
        conn, graph = FakeConn(), FakeGraph()
        return lek.load(conn, graph, p), conn, graph


class LekTests(unittest.TestCase):
    def test_real_file_counts(self):
        conn, graph = FakeConn(), FakeGraph()
        accepted, quarantined, bad = lek.load(conn, graph)
        self.assertEqual((accepted, quarantined, len(bad)), (4965, 60, 20))
        self.assertEqual(conn.kinds().count("put"), 4965)
        self.assertEqual(conn.kinds().count("quarantine"), 60)
        self.assertEqual(graph.runs, 4965)

    def test_header_with_correct_spelling_is_a_loud_error(self):
        with self.assertRaises(ValueError) as cm:
            load_text(HEADER.replace("resodual", "residual") + "\n1;95;0.1;0.5;0.1;0.2\n")
        self.assertIn("resodual_solvent", str(cm.exception))

    def test_planted_part_over_total_quarantines_three_impurity_facts(self):
        (a, q, bad), conn, _ = load_text(HEADER + "\n1;95;0.1;0.5;0.1;0.9\n")
        self.assertEqual((a, q, bad), (2, 3, {"1"}))
        reasons = [(c[1][2], c[1][3]) for c in conn.calls if "gate_quarantine" in c[0]]
        self.assertEqual(reasons, [(lek.CROSS_FIELD, "part > total")] * 3)
        facts = {json.loads(c[1][4])["fact_id"] for c in conn.calls if "gate_quarantine" in c[0]}
        self.assertEqual(facts, {"LEK-1-impurity_o", "LEK-1-impurity_l", "LEK-1-impurities_total"})

    def test_clean_row_all_five_accepted(self):
        (a, q, bad), _, _ = load_text(HEADER + "\n1;95;0.1;0.5;0.1;0.2\n")
        self.assertEqual((a, q, bad), (5, 0, set()))

    def test_part_equal_to_total_is_fine(self):
        (a, q, _), _, _ = load_text(HEADER + "\n1;95;0.1;0.5;0.5;0.2\n")
        self.assertEqual((a, q), (5, 0))

    def test_non_number_cell_quarantined_not_crash(self):
        (a, q, bad), conn, _ = load_text(HEADER + "\n1;95;0.1;0.5;abc;0.2\n")
        self.assertEqual((a, q, bad), (4, 1, set()))
        self.assertEqual(conn.kinds().count("quarantine"), 1)

    def test_source_pointer_row_number_and_exact_text(self):
        _, conn, _ = load_text(HEADER + "\n7;95.50;0.10;0.50;0.10;0.20\n")
        puts = [c[1] for c in conn.calls if "gate_insert_fact" in c[0]]
        self.assertTrue(any("row=2" in str(p) and "95.50" in str(p) for p in puts))

    def test_every_loaded_fact_has_doc_and_original_lineage(self):
        row = {"batch": "1", "dissolution_av": "95", "resodual_solvent": "0.1",
               "impurities_total": "0.5", "impurity_o": "0.1", "impurity_l": "0.2"}
        c = lek._candidate(row, "dissolution_av", 2)
        self.assertEqual((c["source"]["doc_id"], c["lineage"], c["source"]["locator"]), ("Laboratory.csv", "original", "row=2"))


if __name__ == "__main__":
    unittest.main()
