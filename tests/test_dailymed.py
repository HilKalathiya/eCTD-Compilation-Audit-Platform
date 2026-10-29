"""Tests that the DailyMed loader finds every strength in both label versions and that each xml locator points at it."""
import unittest
import xml.etree.ElementTree as ET

from ectd_engine.facts import schema
from ectd_engine.gate import gate
from ectd_engine.loaders import dailymed

ROOTS = {f: ET.parse(dailymed.ROOT / f).getroot() for f in dailymed.FILES}


class TestDailymed(unittest.TestCase):
    def setUp(self):
        self.cands = dailymed.build()

    def strengths(self, version):
        return {c["value"] for c in self.cands if c["source"]["doc_version"] == version}

    def test_strengths_per_version(self):
        self.assertEqual(self.strengths("1"), {"10", "20"})
        self.assertEqual(self.strengths("12"), {"10", "20", "40"})

    def test_same_set_id_and_valid_facts(self):
        self.assertEqual({c["source"]["doc_id"] for c in self.cands}, {"fc726765-5d5a-4d6e-b037-b847bda9fb7c"})
        self.assertEqual(len({c["fact_id"] for c in self.cands}), len(self.cands))
        for c in self.cands:
            self.assertEqual((c["test"], c["unit"], c["lineage"]), ("Strength", "mg", "original"))
            self.assertIsInstance(c["value"], str)
            gate._contract(c)

    def test_every_locator_resolves_to_element_holding_the_value(self):
        for c in self.cands:
            path = c["source"]["locator"].removeprefix("xml=")
            root = ROOTS[dailymed.FILES[0] if c["source"]["doc_version"] == "1" else dailymed.FILES[1]]
            el = dailymed.resolve(root, path)
            self.assertIsNotNone(el, path)
            self.assertTrue(el.tag.endswith("numerator"))
            self.assertEqual(el.get("value"), c["value"])

    def test_resolver_can_fail(self):
        root = ROOTS[dailymed.FILES[0]]
        self.assertIsNone(dailymed.resolve(root, "/document/nonsense[1]"))
        self.assertIsNone(dailymed.resolve(root, "/document/id[9]"))

    def test_gate_accepts_all_in_dry_run(self):
        dry = dailymed._Dry()
        results = dailymed.load(dry, dry)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(isinstance(r, gate.Accepted) for _, r in results))

    def test_planted_bad_unit_or_range_is_not_accepted(self):
        dry = dailymed._Dry()
        rules = gate.load_rules()
        bad = dict(self.cands[0], value="5000")
        self.assertIsInstance(gate.submit(bad, {dailymed.BATCH}, dry, rules, dry), gate.Quarantined)

    def test_sha256_in_sources_md(self):
        import hashlib
        text = (dailymed.ROOT / "data/public/SOURCES.md").read_text(encoding="utf-8")
        for f in dailymed.FILES:
            self.assertIn(hashlib.sha256((dailymed.ROOT / f).read_bytes()).hexdigest(), text)


if __name__ == "__main__":
    unittest.main()
