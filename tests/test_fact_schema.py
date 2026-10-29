"""Tests that the Fact record keeps exact numbers and refuses every kind of loose data."""
import json
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from ectd_engine.facts.schema import Fact, SourcePointer, from_json, to_json


def make_fact(**over):
    base = dict(
        fact_id="F-0001",
        value=Decimal("0.140"),
        unit="%",
        batch="B1",
        test="Impurity A",
        condition="25C/60%RH",
        month=6,
        source=SourcePointer("DOC-1", "v1", "row=12"),
        lineage="original",
        definition="Impurity A result at month 6",
    )
    base.update(over)
    return Fact(**base)


class RoundTrip(unittest.TestCase):
    def test_round_trip_equal(self):
        """UR-02, UR-08: a fact survives to_json/from_json unchanged."""
        f = make_fact()
        self.assertEqual(from_json(to_json(f)), f)

    def test_keeps_trailing_zero(self):
        """UR-08: Decimal 0.140 keeps its zero after the round trip."""
        self.assertEqual(str(from_json(to_json(make_fact())).value), "0.140")

    def test_json_value_is_string(self):
        """UR-08: the JSON stores the value as a string, not a number."""
        self.assertEqual(json.loads(to_json(make_fact()))["value"], "0.140")

    def test_json_keys_sorted(self):
        """UR-18: same fact gives the same JSON text every time."""
        keys = list(json.loads(to_json(make_fact())))
        self.assertEqual(keys, sorted(keys))

    def test_month_none_and_all_locators_ok(self):
        """UR-02: month may be None and all three locator forms are accepted."""
        for loc in ("row=12", "page=4;box=1,2,3.5,4", "cell=B7"):
            f = make_fact(month=None, source=SourcePointer("D", "v1", loc))
            self.assertEqual(from_json(to_json(f)), f)

    def test_all_lineages_ok(self):
        """UR-04: original, copy and unknown are the allowed lineages."""
        for lin in ("original", "copy", "unknown"):
            self.assertEqual(make_fact(lineage=lin).lineage, lin)

    def test_frozen(self):
        """UR-06: a stored fact cannot be edited in place."""
        with self.assertRaises(FrozenInstanceError):
            make_fact().unit = "mg"


class PlantedErrors(unittest.TestCase):
    def test_float_refused(self):
        """UR-08, RK-05: float 0.14 is refused."""
        with self.assertRaises(ValueError):
            make_fact(value=0.14)

    def test_int_refused(self):
        """UR-08, RK-05: int 5 is refused."""
        with self.assertRaises(ValueError):
            make_fact(value=5)

    def test_nan_refused(self):
        """UR-03, RK-06: NaN is refused."""
        with self.assertRaises(ValueError):
            make_fact(value=Decimal("NaN"))

    def test_infinity_refused(self):
        """UR-03, RK-06: Infinity is refused."""
        with self.assertRaises(ValueError):
            make_fact(value=Decimal("Infinity"))

    def test_empty_fact_id_refused(self):
        """UR-02, RK-03: empty fact_id is refused."""
        with self.assertRaises(ValueError):
            make_fact(fact_id="")

    def test_empty_unit_refused(self):
        """UR-03, RK-06: empty unit is refused."""
        with self.assertRaises(ValueError):
            make_fact(unit=" ")

    def test_empty_test_refused(self):
        """UR-10, RK-02: empty test name is refused."""
        with self.assertRaises(ValueError):
            make_fact(test="")

    def test_empty_doc_id_refused(self):
        """UR-02, RK-03: empty doc_id is refused."""
        with self.assertRaises(ValueError):
            SourcePointer("", "v1", "row=1")

    def test_empty_doc_version_refused(self):
        """UR-02, RK-03: empty doc_version is refused."""
        with self.assertRaises(ValueError):
            SourcePointer("D", "", "row=1")

    def test_empty_locator_refused(self):
        """UR-02, RK-03, UR-13: empty locator is refused."""
        with self.assertRaises(ValueError):
            SourcePointer("D", "v1", "")

    def test_negative_month_refused(self):
        """UR-10, RK-02: month -1 is refused."""
        with self.assertRaises(ValueError):
            make_fact(month=-1)

    def test_bad_lineage_refused(self):
        """UR-04, RK-04: lineage 'guess' is refused."""
        with self.assertRaises(ValueError):
            make_fact(lineage="guess")

    def test_bad_locator_refused(self):
        """UR-02, UR-13, RK-14: locator 'p4' is refused."""
        with self.assertRaises(ValueError):
            SourcePointer("D", "v1", "p4")

    def test_json_number_value_refused(self):
        """UR-08, RK-05: JSON with value as number 0.14 is refused on load."""
        d = json.loads(to_json(make_fact()))
        d["value"] = 0.14
        with self.assertRaises(ValueError):
            from_json(json.dumps(d))

    def test_json_rechecks_fields(self):
        """UR-02, RK-03: from_json re-runs the checks (empty doc_version in JSON)."""
        d = json.loads(to_json(make_fact()))
        d["source"]["doc_version"] = ""
        with self.assertRaises(ValueError):
            from_json(json.dumps(d))

    def test_json_garbage_value_refused(self):
        """UR-08: a non-numeric value string is refused on load."""
        d = json.loads(to_json(make_fact()))
        d["value"] = "abc"
        with self.assertRaises(ValueError):
            from_json(json.dumps(d))

    def test_empty_batch_refused(self):
        """UR-10, RK-02: empty batch is refused."""
        with self.assertRaises(ValueError):
            make_fact(batch="")

    def test_empty_condition_refused(self):
        """UR-10, RK-02: empty condition is refused."""
        with self.assertRaises(ValueError):
            make_fact(condition="")

    def test_na_batch_and_condition_accepted(self):
        """UR-10: the literal 'n/a' is allowed when a fact has no batch or condition."""
        f = make_fact(batch="n/a", condition="n/a")
        self.assertEqual(from_json(to_json(f)), f)

    def _load_with_value(self, raw):
        d = json.loads(to_json(make_fact()))
        d["value"] = raw
        return from_json(json.dumps(d))

    def test_value_with_spaces_refused(self):
        """UR-08, RK-05: value ' 0.14 ' (spaces) is refused on load."""
        with self.assertRaises(ValueError):
            self._load_with_value(" 0.14 ")

    def test_value_with_exponent_refused(self):
        """UR-08, RK-05: value '1e3' (exponent) is refused on load."""
        with self.assertRaises(ValueError):
            self._load_with_value("1e3")

    def test_extra_json_key_refused(self):
        """UR-06, RK-03: an unknown JSON key 'note' is refused on load."""
        d = json.loads(to_json(make_fact()))
        d["note"] = "hidden"
        with self.assertRaises(ValueError):
            from_json(json.dumps(d))

    def test_extra_source_key_refused(self):
        """UR-02, RK-03: an unknown key inside source is refused on load."""
        d = json.loads(to_json(make_fact()))
        d["source"]["note"] = "hidden"
        with self.assertRaises(ValueError):
            from_json(json.dumps(d))


if __name__ == "__main__":
    unittest.main()
