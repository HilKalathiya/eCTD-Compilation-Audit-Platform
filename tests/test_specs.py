"""Tests the Lek spec facts, the P.5.1 table and the P.5.6 justification facts, with planted errors that must be caught."""
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from ectd_engine.facts.schema import Fact, SourcePointer
from ectd_engine.rules import q3b
from ectd_engine.specs import load, p51, p56

HEADER = "attribute,limit_kind,value,unit,basis,basis_note\n"
GOOD = {
    "impurity_o": "impurity_o,NMT,,%,q3b_qualification,computed by code from Q3B at assumed MDD\n",
    "impurity_l": "impurity_l,NMT,,%,q3b_qualification,computed by code from Q3B at assumed MDD\n",
    "impurities_total": "impurities_total,NMT,1.0,%,declared,declared for demo; no public source\n",
    "dissolution_av": "dissolution_av,NLT,80,%,declared,declared for demo; no public source\n",
    "resodual_solvent": "resodual_solvent,NMT,0.5,%,declared,declared for demo; no public source\n",
}
TABLE = q3b.load()


def spec_file(**changes):
    """A temporary copy of the spec with some lines replaced (None = line removed)."""
    lines = dict(GOOD)
    for k, v in changes.items():
        if v is None:
            del lines[k]
        else:
            lines[k] = v
    d = tempfile.mkdtemp()
    p = Path(d) / "spec.csv"
    p.write_text(HEADER + "".join(lines.values()), encoding="utf-8")
    return p


def fact(fid, value):
    return Fact(fid, Decimal(value), "%", "b", "t", "batch release", None, SourcePointer("x", "v1", "row=2"), "original", "d")


class FakeStore:
    """Batch facts for one attribute at a time: {batch: value or None (= quarantined, no fact)}."""

    def __init__(self, values):
        self.values = values
        self.known_batches = set(values)

    def get(self, fid):
        for b, v in self.values.items():
            if v is not None and fid.startswith(f"LEK-{b}-"):
                return fact(fid, v)
        return None


class RealSpecTests(unittest.TestCase):
    def test_real_spec_values_and_basis(self):
        s = load.load(table=TABLE)
        self.assertEqual(s.mdd.value, Decimal("40"))
        self.assertEqual(s.mdd.fact_id, "ASSUMPTION-MDD")
        by = {r.attribute: r for r in s.rows}
        self.assertEqual(by["impurity_o"].fact.value, Decimal("0.5"))
        self.assertEqual(by["impurity_o"].fact.fact_id, "SPEC-LEK-impurity_o")
        self.assertEqual(by["impurity_o"].rule_id, "Q3B_R2@2006-06-02:qualification:2")
        self.assertEqual(by["impurity_o"].fact.lineage, "original")
        self.assertEqual(by["impurities_total"].fact.value, Decimal("1.0"))
        # declared rows never look sourced
        self.assertEqual(by["impurities_total"].fact.lineage, "unknown")
        self.assertTrue(by["impurities_total"].fact.definition.startswith("DECLARED"))
        self.assertIsNone(by["impurities_total"].rule_id)

    def test_p51_table_lines(self):
        text = p51.render(load.load(table=TABLE))
        self.assertIn("| Impurity O | NMT 0.5 % | ICH Q3B(R2) qualification", text)
        self.assertIn("| Dissolution | NLT 80 % | Declared for demo (no public source) |", text)
        self.assertEqual(len(text.splitlines()), 7)


class PlantedSpecTests(unittest.TestCase):
    def test_mdd_5_changes_the_q3b_rule_not_just_the_number(self):
        s40 = load.load(table=TABLE)
        s5 = load.load(path=spec_file(), mdd=Decimal("5"), table=TABLE)
        a, b = s40.rows[1], s5.rows[1]
        self.assertEqual(a.attribute, "impurity_o")
        self.assertNotEqual(a.rule_id, b.rule_id)
        self.assertEqual(b.rule_id, "Q3B_R2@2006-06-02:qualification:1")
        self.assertEqual(b.fact.value, Decimal("1.0"))
        self.assertIn("5 mg", b.fact.definition)

    def test_typed_value_in_q3b_row_rejected(self):
        p = spec_file(impurity_o="impurity_o,NMT,0.3,%,q3b_qualification,typed\n")
        with self.assertRaisesRegex(load.SpecRefused, "impurity_o.*typed value"):
            load.load(path=p, table=TABLE)

    def test_declared_row_claiming_q3b_rejected(self):
        p = spec_file(impurities_total="impurities_total,NMT,1.0,%,declared,from ICH Q3B table\n")
        with self.assertRaisesRegex(load.SpecRefused, "impurities_total.*claim a source"):
            load.load(path=p, table=TABLE)

    def test_declared_row_blank_value_rejected(self):
        p = spec_file(dissolution_av="dissolution_av,NLT,,%,declared,declared for demo\n")
        with self.assertRaisesRegex(load.SpecRefused, "dissolution_av.*blank"):
            load.load(path=p, table=TABLE)

    def test_missing_attribute_row_rejected(self):
        with self.assertRaisesRegex(load.SpecRefused, "resodual_solvent"):
            load.load(path=spec_file(resodual_solvent=None), table=TABLE)

    def test_gate_still_rules(self):
        p = spec_file(resodual_solvent="resodual_solvent,NMT,5,%,declared,declared for demo\n")
        with self.assertRaisesRegex(load.SpecRefused, "RANGE_OUT"):
            load.load(path=p, table=TABLE)

    def test_p51_refuses_when_a_spec_fact_is_missing(self):
        s = load.load(table=TABLE)
        broken = replace(s, rows=tuple(r for r in s.rows if r.attribute != "impurity_l"))
        with self.assertRaisesRegex(p51.SpecIncomplete, "impurity_l"):
            p51.render(broken)
        no_fact = replace(s, rows=tuple(replace(r, fact=None) if r.attribute == "dissolution_av" else r for r in s.rows))
        with self.assertRaisesRegex(p51.SpecIncomplete, "dissolution_av"):
            p51.render(no_fact)


class P56Tests(unittest.TestCase):
    def test_batch_outside_limit_counted(self):
        s = load.load(table=TABLE)
        row = s.rows[1]  # impurity_o, NMT 0.5
        n, lo, hi, out = p56.batch_support(row, FakeStore({"1": "0.1", "2": "0.5", "3": "0.7", "4": "0.9", "5": None}))
        self.assertEqual((n, lo, hi, out), (4, Decimal("0.1"), Decimal("0.9"), 2))  # 0.5 is inside; quarantined 5 is left out
        row = s.rows[0]  # dissolution NLT 80
        n, lo, hi, out = p56.batch_support(row, FakeStore({"1": "79.4", "2": "80", "3": "95"}))
        self.assertEqual((n, lo, hi, out), (3, Decimal("79.4"), Decimal("95"), 1))

    def test_justification_has_quote_page_and_support(self):
        s = load.load(table=TABLE)
        items = p56.compute(s, FakeStore({"1": "0.1", "2": "0.2"}))
        j = {i.attribute: i for i in items}["impurity_o"]
        self.assertEqual((j.page, j.limit, j.n, j.outside), (11, Decimal("0.5"), 2, 0))
        self.assertIn("10 mg - 100 mg 0.5% or 200", j.quote)
        self.assertIsNone({i.attribute: i for i in items}["impurities_total"].quote)

    def test_altered_quote_fails_cite(self):
        s = load.load(table=TABLE)
        bad_rows = tuple(replace(r, source_quote=r.source_quote.replace("0.5%", "0.9%")) if r.rule_id.endswith("qualification:2") else r
                         for r in TABLE.rows)
        with self.assertRaisesRegex(p56.JustificationRefused, "does not verify"):
            p56.compute(s, FakeStore({"1": "0.1"}), table=q3b.Table(bad_rows))

    def test_limit_changed_after_load_is_caught(self):
        s = load.load(table=TABLE)
        rows = tuple(replace(r, fact=replace(r.fact, value=Decimal("0.9"))) if r.attribute == "impurity_o" else r for r in s.rows)
        with self.assertRaisesRegex(p56.JustificationRefused, "does not match Q3B"):
            p56.compute(replace(s, rows=rows), FakeStore({"1": "0.1"}))


if __name__ == "__main__":
    unittest.main()
