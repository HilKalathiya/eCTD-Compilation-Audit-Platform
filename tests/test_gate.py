"""Tests the write gate without a database, using a fake connection that records what would be stored."""
import json
import unittest
from decimal import Decimal
from pathlib import Path

from ectd_engine.facts import schema
from ectd_engine.gate import gate

REGISTRY = {"B1", "B2", "B3"}
RULES_DIR = Path(gate.__file__).resolve().parent / "rules"


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


def cand(**over):
    d = {"fact_id": "F1", "value": "0.14", "unit": "%", "batch": "B1", "test": "Impurity A",
         "condition": "25C/60%RH", "month": 6,
         "source": {"doc_id": "DOC-1", "doc_version": "v1", "locator": "row=12"},
         "lineage": "original", "definition": "Impurity A at month 6"}
    d.update(over)
    return d


def run(c):
    conn = FakeConn()
    return gate.submit(c, REGISTRY, conn), conn


class GateTests(unittest.TestCase):
    def test_good_candidate_accepted_and_stored(self):
        r, conn = run(cand())
        self.assertIsInstance(r, gate.Accepted)
        self.assertEqual(conn.kinds(), ["put"])

    def test_unknown_batch_quarantined(self):
        r, conn = run(cand(batch="B99"))
        self.assertEqual(r.reason_code, gate.BATCH_UNKNOWN)
        self.assertEqual(conn.kinds(), ["quarantine"])

    def test_unit_swap_mg_quarantined(self):
        r, conn = run(cand(unit="mg"))
        self.assertEqual(r.reason_code, gate.UNIT_NOT_ALLOWED)
        self.assertEqual(conn.kinds(), ["quarantine"])

    def test_decimal_shift_out_of_range_quarantined(self):
        r, conn = run(cand(value="1.4"))
        self.assertEqual(r.reason_code, gate.RANGE_OUT)
        self.assertEqual(conn.kinds(), ["quarantine"])

    def test_missing_unit_quarantined(self):
        c = cand()
        del c["unit"]
        r, _ = run(c)
        self.assertEqual(r.reason_code, gate.FIELD_MISSING)
        self.assertIn("unit", r.reason_text)

    def test_blank_unit_quarantined(self):
        r, _ = run(cand(unit="\t"))
        self.assertEqual(r.reason_code, gate.FIELD_MISSING)

    def test_missing_source_pointer_quarantined(self):
        r, _ = run(cand(source={"doc_id": "D", "doc_version": "v1", "locator": ""}))
        self.assertEqual(r.reason_code, gate.FIELD_MISSING)

    def test_bad_locator_is_contract_invalid(self):
        r, _ = run(cand(source={"doc_id": "D", "doc_version": "v1", "locator": "anywhere"}))
        self.assertEqual(r.reason_code, gate.CONTRACT_INVALID)

    def test_unknown_test_quarantined_not_guessed(self):
        r, _ = run(cand(test="Mystery"))
        self.assertEqual(r.reason_code, gate.TEST_UNKNOWN)

    def test_honest_gap_decimal_shift_inside_range_is_not_caught(self):
        """Known gap: 0.14 -> 0.014 stays inside 0 to 1.0, so this gate accepts it.

        Only C1.4 (two-route agreement: the same number read two independent ways) can catch it.
        """
        r, conn = run(cand(value="0.014"))
        self.assertIsInstance(r, gate.Accepted)
        self.assertEqual(conn.kinds(), ["put"])

    def test_ppm_converted_by_table_exactly(self):
        r, _ = run(cand(value="1400", unit="ppm"))
        self.assertIsInstance(r, gate.Accepted)
        self.assertEqual(r.fact.unit, "%")
        self.assertEqual(r.fact.value, Decimal("0.1400"))
        self.assertIn("converted from 1400 ppm", r.fact.definition)

    def test_converted_value_still_range_checked(self):
        r, _ = run(cand(value="14000", unit="ppm"))  # = 1.4 %
        self.assertEqual(r.reason_code, gate.RANGE_OUT)

    def test_range_edges_inclusive(self):
        self.assertIsInstance(run(cand(value="1.0"))[0], gate.Accepted)
        self.assertIsInstance(run(cand(value="0", fact_id="F2"))[0], gate.Accepted)
        self.assertEqual(run(cand(value="1.01"))[0].reason_code, gate.RANGE_OUT)

    def test_quarantine_keeps_the_candidate_and_reason(self):
        _, conn = run(cand(batch="B99"))
        params = conn.calls[0][1]
        self.assertEqual(params[2], gate.BATCH_UNKNOWN)
        self.assertEqual(json.loads(params[4])["batch"], "B99")

    def test_nothing_dropped_each_bad_input_leaves_one_quarantine_row(self):
        bad = [cand(batch="B99"), cand(unit="mg"), cand(value="1.4"), cand(unit=None), cand(test="Mystery")]
        conn = FakeConn()
        for c in bad:
            gate.submit(c, REGISTRY, conn)
        self.assertEqual(conn.kinds(), ["quarantine"] * len(bad))

    def test_non_dict_candidate_quarantined(self):
        r, conn = run("0.14")
        self.assertEqual(r.reason_code, gate.CONTRACT_INVALID)
        self.assertEqual(conn.kinds(), ["quarantine"])

    def test_fifty_valid_candidates_all_accepted_no_false_alarms(self):
        tests = [("Impurity A", "%", "0.14"), ("Impurity B", "%", "0.32"), ("Assay", "%", "99.8"),
                 ("Water", "%", "1.2"), ("Dissolution", "%", "98.0")]
        conn = FakeConn()
        results = []
        for i in range(50):
            t, u, v = tests[i % 5]
            results.append(gate.submit(cand(fact_id=f"G{i}", test=t, unit=u, value=v, batch=f"B{i % 3 + 1}"), REGISTRY, conn))
        self.assertEqual(sum(isinstance(r, gate.Accepted) for r in results), 50)
        self.assertEqual(conn.kinds(), ["put"] * 50)


class RuleFileTests(unittest.TestCase):
    def test_range_files_entered_twice_are_identical(self):
        a = (RULES_DIR / "ranges.json").read_text(encoding="utf-8")
        b = (RULES_DIR / "ranges_check.json").read_text(encoding="utf-8")
        self.assertEqual(gate.range_limits(json.loads(a)), gate.range_limits(json.loads(b)))

    def _load_with_check(self, mutate):
        """Copy the rule files to a temp dir, let `mutate` change the check copy, then try to load."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for n in ("units.json", "ranges.json"):
                (d / n).write_text((RULES_DIR / n).read_text(encoding="utf-8"), encoding="utf-8")
            planted = json.loads((RULES_DIR / "ranges.json").read_text(encoding="utf-8"))
            mutate(planted)
            (d / "ranges_check.json").write_text(json.dumps(planted), encoding="utf-8")
            return gate.load_rules(d)

    def test_disagreeing_range_files_refuse_to_load(self):
        with self.assertRaises(ValueError):
            self._load_with_check(lambda p: p["Impurity A"].update(max="10.0"))

    def test_same_number_spelled_differently_loads(self):
        self._load_with_check(lambda p: p["Impurity A"].update(max="1.00", min="0.0"))  # "1.0" vs "1.00", "0" vs "0.0"

    def test_close_but_different_number_refuses_to_load(self):
        with self.assertRaises(ValueError):
            self._load_with_check(lambda p: p["Assay"].update(min="90.1"))
        with self.assertRaises(ValueError):
            self._load_with_check(lambda p: p["Water"].update(max="5.1"))

    def test_extra_test_name_in_one_file_refuses_to_load(self):
        with self.assertRaises(ValueError):
            self._load_with_check(lambda p: p.update({"Extra": {"min": "0", "max": "1"}}))

    def test_non_number_in_range_file_refuses_to_load(self):
        with self.assertRaises(ValueError):
            self._load_with_check(lambda p: p["Impurity A"].update(max="abc"))

    def test_every_test_has_unit_and_range_rule(self):
        units, ranges = gate.load_rules()
        self.assertEqual(set(units), set(ranges))
        for rule in units.values():
            for f in rule["conversions"].values():
                Decimal(f)  # exact decimal strings

    def test_tab_only_definition_refused_by_python(self):
        c = cand(definition="\t\n")
        r, _ = run(c)
        self.assertEqual(r.reason_code, gate.FIELD_MISSING)
        with self.assertRaises(ValueError):
            schema.from_json(json.dumps(c))


if __name__ == "__main__":
    unittest.main()
