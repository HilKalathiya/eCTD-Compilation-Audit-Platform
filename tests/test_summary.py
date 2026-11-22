"""Tests for the 2.3 builder (summary/build.py, plan.py) and the graph fact loader, on in-memory facts; the live graph is never written."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import build
from ectd_engine.summary.plan import PUBLIC_REFS, SUMMARY_PLAN, TITLE, stat_id

LABEL = G.LABEL


def built(facts):
    folder = Path(tempfile.mkdtemp()) / "run"
    return folder, build.write_run(folder, facts)


class Collect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = G.collect()

    def test_every_fact_has_its_own_prefix_and_the_contract_fields(self):
        for fid, row in self.facts.items():
            self.assertTrue(fid.startswith("M23-") and not fid.startswith("DEMO25-"))
            self.assertEqual(row["fact_id"], fid)
            for key in ("value_text", "unit", "test", "condition", "doc_id", "doc_version", "locator", "kind", "family"):
                self.assertTrue(row[key] != "" or key == "condition", (fid, key))
            self.assertIsInstance(row["value_text"], str)

    def test_demo_rows_keep_the_label_and_the_page_public_rows_keep_the_page(self):
        stab = [r for r in self.facts.values() if r["family"] == "stability"]
        self.assertEqual({(r["kind"], r["demo_label"] == LABEL) for r in stab}, {("demo", True), ("public", False)})
        self.assertTrue(all(r["page"].isdigit() for r in stab))
        self.assertTrue(all(r["demo_label"] == LABEL for r in self.facts.values() if r["family"] == "spec"))

    def test_storage_comes_from_the_condition_text_and_says_so(self):
        low = self.facts[G.stab_id("20-25C CRT", "storage_low", "36")]
        high = self.facts[G.stab_id("20-25C CRT", "storage_high", "36")]
        self.assertEqual((low["value_text"], high["value_text"], low["derived"], low["page"]), ("20", "25", "yes", "3"))
        self.assertIn("condition text", low["definition"])

    def test_no_value_was_changed_against_the_csv(self):
        import csv
        with open(G.SF.DEFAULT_CSV, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                row = self.facts[G.stab_id(r["condition"], r["attribute"], r["month"])]
                self.assertEqual((row["value_text"], row["unit"]), (r["value"], r["unit"]))

    def test_the_plan_only_names_facts_that_exist(self):
        for fid in PUBLIC_REFS.values():
            self.assertIn(fid, self.facts)


class FakeSession:
    def __init__(self):
        self.calls = []

    def run(self, cypher, **params):
        self.calls.append((cypher, params))
        return self

    def consume(self):
        pass


class PutAll(unittest.TestCase):
    def test_only_own_labels_are_written_and_values_stay_text(self):
        facts, s = G.collect(), FakeSession()
        self.assertEqual(G.put_all(s, facts), len(facts))
        for cypher, p in s.calls:
            self.assertTrue(("StabFact" in cypher) != ("SpecFact" in cypher))
            self.assertNotIn("DETACH", cypher)
            self.assertNotIn(":Fact ", cypher)
            self.assertTrue(p["fact_id"].startswith("M23-"))
            self.assertIsInstance(p["props"]["value_text"], str)


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = G.collect()
        cls.folder, cls.report = built(cls.facts)

    def test_every_number_is_placed_and_no_digit_is_loose(self):
        r = self.report
        self.assertEqual((r["numbers"], r["placements"], r["data_src"], r["uncovered"], r["rejected"], r["docx_problems"]),
                         (30, 30, 30, 0, [], []))

    def test_placement_ids_are_graph_fact_ids_and_texts_equal_the_stored_values(self):
        for line in (self.folder / "placements.jsonl").read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec["id"].startswith("M23-STAT|"):
                cond, attr, which = rec["id"][len("M23-STAT|"):].split("|")
                vals = [r["value_text"] for r in self.facts.values() if r["condition"] == cond and r["attribute"] == attr and r["kind"] == "demo"]
                self.assertIn(rec["text"], vals)
            else:
                self.assertEqual(rec["text"], self.facts[rec["id"]]["value_text"])

    def test_demo_sentences_start_with_the_label_and_the_public_one_does_not(self):
        html = (self.folder / "M23.html").read_text(encoding="utf-8")
        paras = re.findall(r'<p data-section="(\w+)">(.*?)</p>', html)
        demo = [t for n, t in paras if n in ("spec_intro", "results")]
        self.assertEqual(len(demo), 10)
        self.assertTrue(all(t.startswith(LABEL) for t in demo))
        public = next(t for n, t in paras if n == "public")
        self.assertNotIn("illustrative", public)

    def test_headings_and_title_hold_no_loose_digits(self):
        self.assertFalse(re.search(r"\d", TITLE))
        for part, spec in SUMMARY_PLAN.items():
            self.assertFalse(re.search(r"\d", spec["title"]))

    def test_an_existing_folder_is_refused(self):
        with self.assertRaises(FileExistsError):
            build.write_run(self.folder, self.facts)

    def test_same_facts_give_the_same_files(self):
        other, _ = built(copy.deepcopy(self.facts))
        for name in ("M23.html", "placements.jsonl"):
            self.assertEqual((other / name).read_bytes(), (self.folder / name).read_bytes())

    def test_the_word_file_holds_the_same_numbers(self):
        units = build.saved_units(self.folder / "M23.docx")
        self.assertIn(("row", "Dissolution\tNLT 80%"), units)


class Refusals(unittest.TestCase):
    """A fact that does not fit its place must stop that section (it is reported, never written)."""

    def refused(self, facts):
        _, report = built(facts)
        return report["rejected"]

    def test_a_missing_fact_rejects_its_section(self):
        facts = G.collect()
        del facts[PUBLIC_REFS["shelf"]]
        self.assertTrue(any(why.startswith("missing:") for _, why in self.refused(facts)))

    def test_a_demo_fact_without_the_label_is_refused(self):
        facts = G.collect()
        facts[G.spec_id("dissolution_av")]["demo_label"] = ""
        self.assertTrue(any("label" in why for _, why in self.refused(facts)))

    def test_a_public_fact_with_a_label_is_refused(self):
        facts = G.collect()
        facts[PUBLIC_REFS["shelf"]]["demo_label"] = LABEL
        self.assertTrue(any("public_sentence_holds_demo_fact" in why or "label" in why for _, why in self.refused(facts)))

    def test_an_unlisted_unit_is_refused(self):
        facts = G.collect()
        facts[PUBLIC_REFS["shelf"]]["unit"] = "fortnights"
        self.assertTrue(any(why.startswith("unit_not_listed") for _, why in self.refused(facts)))

    def test_a_missing_result_group_is_refused(self):
        facts = {k: v for k, v in G.collect().items() if not (v["condition"] == "30C/75%RH" and v["attribute"] == "Assay")}
        self.assertTrue(any("missing" in why for _, why in self.refused(facts)))

    def test_stat_ids_name_the_statistic(self):
        self.assertEqual(stat_id("25C/60%RH", "Assay", "min"), "M23-STAT|25C/60%RH|Assay|min")


if __name__ == "__main__":
    unittest.main()
