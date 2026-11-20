"""Tests for the P.5 document builder: the content plan, the number-to-fact placements, and the planted errors each gate must catch."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from ectd_engine.render import plan
from ectd_engine.render.html import (Paragraph, Rejected, Section, build_document, build_p54, build_p56, check_section,
                                     make_paragraph, uncovered_in_html, visible_numbers)
from ectd_engine.render.numbers import EXEMPT_KINDS, exempt_spans, find_numbers, uncovered_digits
from ectd_engine.writer.spec_facts import compute_spec_facts

TASK56 = {"task_id": "t1", "section": "3.2.P.5.6", "product": "Lek tablets", "attribute": "Dissolution",
          "column": "dissolution_av", "limit_kind": "NLT", "limit": "80", "unit": "%", "basis": "declared",
          "n": 28, "min": "84.33", "max": "97.33", "n_outside": 0}
TEXT56 = ("The acceptance criterion for [[attribute_dummy]] is [[limit_kind]] [[limit]], [[basis]]. "
          "Results for [[n_batches]] ranged from [[min_value]] to [[max_value]].").replace("[[attribute_dummy]]", "Dissolution")
TASK54 = {"task_id": "b1", "section": "3.2.P.5.4", "product": "Lek tablets", "attribute": "Dissolution",
          "column": "dissolution_av", "unit": "%", "decimals": 2, "batches": ["26", "105"]}


def facts56():
    facts, flags, _ = compute_spec_facts(TASK56)
    return facts, flags


def facts54():
    from ectd_engine.writer.batch_facts import compute_batch_facts, fact_id
    vals = {"26": "97.33", "105": "92.33"}

    def get(fid):
        return next((_fact(fid, v, b) for b, v in vals.items() if fid == fact_id(b, "dissolution_av")), None)
    return compute_batch_facts(TASK54, get, {"26", "105"})


def _fact(fid, v, b):
    from types import SimpleNamespace
    from decimal import Decimal
    return SimpleNamespace(fact_id=fid, value=Decimal(v), unit="%", batch=b)


TEXT54 = "Dissolution results for [[n_batches]] ranged from [[min_value]] to [[max_value]], with a mean of [[mean_value]]."


class PlanTests(unittest.TestCase):
    def test_parts_and_sections_are_in_a_fixed_order(self):
        self.assertEqual(plan.parts(), ["3.2.P.5.4", "3.2.P.5.6"])
        self.assertEqual([s["name"] for s in plan.CONTENT_PLAN["3.2.P.5.4"]["sections"]], ["opening", "table", "discussion"])

    def test_conditions_come_from_the_flags(self):
        self.assertEqual(plan.conditions("3.2.P.5.6", {"basis": "q3b_qualification", "n_outside": 2}), {"q3b", "outside"})
        self.assertEqual(plan.conditions("3.2.P.5.6", {"basis": "declared", "n_outside": 0}), set())
        self.assertEqual(plan.conditions("3.2.P.5.4", {"n_excluded": 1}), {"excluded"})

    def test_required_keys_grow_with_conditions(self):
        base = plan.required_keys("3.2.P.5.6", "justification", set())
        more = plan.required_keys("3.2.P.5.6", "justification", {"q3b", "outside"})
        self.assertEqual(set(more) - set(base), {"mdd", "q3b_quote", "n_outside"})


class NumberFinderTests(unittest.TestCase):
    def test_finds_digits_decimals_and_number_words(self):
        self.assertEqual([t for _, t in find_numbers("0.7% of 24 and eleven")], ["0.7", "24", "eleven"])

    def test_every_exempt_kind_is_listed_and_each_hides_only_itself(self):
        self.assertEqual(EXEMPT_KINDS, ("guideline_or_section_name", "batch_id_in_text", "batch_id_table_cell"))
        self.assertEqual(find_numbers("ICH Q3B(R2) in 3.2.P.5.4"), [])
        self.assertEqual(find_numbers("Batches 28, 31 and 97", {"28", "31", "97"}), [])
        self.assertEqual(find_numbers("26\t97.33\t%", {"26"}, table_first_cell=True), [(3, "97.33")])

    def test_planted_a_number_next_to_an_exempt_token_is_still_found(self):
        self.assertEqual([t for _, t in find_numbers("Batches 28, 31 and 0.7%", {"28", "31"})], ["0.7"])
        self.assertEqual([t for _, t in find_numbers("Batch 99999", {"28"})], ["99999"])
        self.assertEqual([t for _, t in find_numbers("ICH Q3B(R2) says 0.7%")], ["0.7"])
        self.assertEqual([t for _, t in find_numbers("26\t97.33", {"28"}, table_first_cell=True)], ["26", "97.33"])


class WiderFinderTests(unittest.TestCase):
    def test_finds_ordinals_fractions_leading_dot_and_thousands(self):
        self.assertEqual([t for _, t in find_numbers("the first and twentieth, ½ ¼ ¾")],
                         ["first", "twentieth", "½", "¼", "¾"])
        self.assertEqual([t for _, t in find_numbers("lost .5% of 1,000 and 12,345.6")], [".5", "1,000", "12,345.6"])

    def test_ordinal_inside_another_word_is_not_a_number(self):
        self.assertEqual(find_numbers("secondary and firstly"), [])

    def test_second_check_sees_digits_without_the_number_regex(self):
        self.assertEqual(uncovered_digits("lost 7 of it", []), ["uncovered:lost 7 of it"])
        self.assertEqual(uncovered_digits("lost 7 of it", [(5, 6)]), [])
        self.assertEqual(uncovered_digits("in 3.2.P.5.4 and Batch 26", [], {"26"}), [])
        self.assertTrue(uncovered_digits("Batch 27", [], {"26"}))
        self.assertEqual(uncovered_digits("no digits, only first and ½", []), [])


class BuildTests(unittest.TestCase):
    def build56(self, facts=None, flags=None, text=TEXT56):
        f, fl = facts56()
        return build_p56(TASK56, facts if facts is not None else f, flags if flags is not None else fl, text)

    def test_p56_section_is_built_and_every_number_is_placed(self):
        (sec,) = self.build56()
        self.assertIsInstance(sec, Section)
        self.assertEqual(check_section(sec), [])
        ids = {pl["id"] for pl in sec.paragraphs[0].placements}
        self.assertEqual(ids, {"limit", "n_batches", "min_value", "max_value"})

    def test_p54_builds_opening_table_and_discussion(self):
        facts, flags, _, table = facts54()
        secs = build_p54(TASK54, facts, flags, table, TEXT54)
        self.assertEqual([type(s) for s in secs], [Section] * 3)
        cells = [pl["id"] for pl in secs[1].paragraphs[0].placements]
        self.assertEqual(cells, ["LEK-26-dissolution_av"])

    def test_gate_a_planted_dropped_fact_is_rejected_as_missing(self):
        facts, flags = facts56()
        del facts["max_value"]
        (r,) = self.build56(facts=facts, flags=flags)
        self.assertIsInstance(r, Rejected)
        self.assertEqual(r.reason, "missing:max_value")

    def test_gate_a_planted_dropped_conditional_fact_is_rejected(self):
        facts, flags = facts56()
        flags = dict(flags, basis="q3b_qualification")
        (r,) = self.build56(facts=facts, flags=flags)
        self.assertTrue(r.reason.startswith("missing:"), r.reason)

    def test_gate_a_text_that_asks_for_an_absent_fact_is_rejected(self):
        (r,) = self.build56(text=TEXT56 + " The mean was [[mean_value]].")
        self.assertEqual(r.reason, "missing:mean_value")

    def test_gate_b_planted_bare_number_is_caught(self):
        (sec,) = self.build56()
        bad = copy.deepcopy(sec)
        bad.paragraphs[0].text += " About 0.7% was lost."
        self.assertIn("unplaced:0.7", check_section(bad))

    def test_gate_b_bare_number_in_the_template_is_rejected_by_the_build(self):
        (r,) = self.build56(text=TEXT56 + " Loss was 0.7%.")
        self.assertIsInstance(r, Rejected)
        self.assertEqual(r.reason, "unplaced:0.7")

    def test_gate_b_five_planted_hiding_places_are_each_caught(self):
        for extra, reason, digit in ((" Loss was .5%.", "unplaced:", True), (" Loss was 1,000 units.", "unplaced:", True),
                                     (" Loss was ½ of it.", "unplaced:", False), (" The first batch failed.", "unplaced:first", False)):
            with self.subTest(extra=extra):
                (r,) = self.build56(text=TEXT56 + extra)
                self.assertIsInstance(r, Rejected)
                self.assertTrue(r.reason.startswith(reason), r.reason)
                self.assertEqual(any(p.startswith("uncovered:") for p in r.problems), digit)

    def test_gate_b_digit_in_a_table_id_cell_not_on_the_batch_list_is_caught(self):
        facts, flags, _, table = facts54()
        bad = copy.deepcopy(table)
        bad["rows"][0] = ("99", bad["rows"][0][1])        # 99 is not one of the task's batches
        secs = build_p54(TASK54, facts, flags, bad, TEXT54)
        self.assertIsInstance(secs[1], Rejected)
        self.assertTrue(any(p.startswith("uncovered:99") for p in secs[1].problems), secs[1].problems)

    def test_second_check_catches_digits_even_if_the_number_regex_were_blind(self):
        from unittest import mock
        import ectd_engine.render.html as h
        (sec,) = self.build56()
        bad = copy.deepcopy(sec)
        bad.paragraphs[0].text += " Loss was 0.7%."
        with mock.patch.object(h, "find_numbers", lambda *a, **k: []):
            problems = h.check_section(bad)
        self.assertFalse(any(p.startswith("unplaced:") for p in problems))
        self.assertTrue(any(p.startswith("uncovered:") for p in problems))

    def test_gate_b_planted_placement_with_no_number_is_caught(self):
        (sec,) = self.build56()
        bad = copy.deepcopy(sec)
        bad.paragraphs[0].placements.append({"id": "limit", "label": "", "offset": 4, "text": "The"})
        self.assertIn("badplacement:The", check_section(bad))

    def test_gate_b_planted_placement_at_the_wrong_offset_is_caught(self):
        (sec,) = self.build56()
        bad = copy.deepcopy(sec)
        bad.paragraphs[0].placements[0]["offset"] += 1
        problems = check_section(bad)
        self.assertTrue(any(p.startswith("badplacement:") for p in problems))
        self.assertTrue(any(p.startswith("unplaced:") for p in problems))

    def test_gate_b_planted_duplicate_placement_is_caught(self):
        (sec,) = self.build56()
        bad = copy.deepcopy(sec)
        bad.paragraphs[0].placements.append(dict(bad.paragraphs[0].placements[0]))
        self.assertIn("badplacement:two placements for one number", check_section(bad))

    def test_the_wording_repair_still_sees_the_count(self):
        task = dict(TASK56, n_outside=1)
        facts, flags, _ = compute_spec_facts(task)
        text = "[[n_outside]] of [[n_batches]] results were outside [[limit_kind]] [[limit]], [[basis]]."
        (sec,) = build_p56(task, facts, flags, text)
        self.assertIsInstance(sec, Section)
        self.assertIn("1 of 28 results was", sec.paragraphs[0].text)


class DocumentTests(unittest.TestCase):
    def doc(self):
        facts, flags, _, table = facts54()
        f56, fl56 = facts56()
        items = [
            {"part": "3.2.P.5.6", "task_id": "t1", "attribute": "Dissolution", "batch_ids": [],
             "sections": build_p56(TASK56, f56, fl56, TEXT56)},
            {"part": "3.2.P.5.4", "task_id": "b1", "attribute": "Dissolution", "batch_ids": ["26", "105"],
             "sections": build_p54(TASK54, facts, flags, table, TEXT54)},
        ]
        return build_document(items)

    def test_numbers_equal_placements_and_html_marks(self):
        doc, records, report = self.doc()
        self.assertEqual(report["numbers"], report["placements"])
        self.assertEqual(report["placements"], report["data_src"])
        self.assertEqual(len(records), report["placements"])
        self.assertEqual(report["missing"], 0)

    def test_the_plan_orders_the_parts_not_the_input(self):
        doc, _, _ = self.doc()
        self.assertLess(doc.index('data-part="3.2.P.5.4"'), doc.index('data-part="3.2.P.5.6"'))

    def test_every_record_has_the_five_fields_and_points_at_its_number(self):
        _, records, _ = self.doc()
        for r in records:
            self.assertTrue({"id", "section", "paragraph", "offset", "text"} <= set(r))
            self.assertTrue(r["id"] and r["text"])

    def test_planted_bare_number_in_the_html_is_caught(self):
        doc, records, report = self.doc()
        bad = doc.replace("</body>", "<p>About 0.7% was lost.</p></body>")
        self.assertEqual(len(visible_numbers(bad, {"26", "105"})), report["numbers"] + 1)
        self.assertEqual(len(visible_numbers(doc, {"26", "105"})), report["numbers"])

    def test_planted_digits_in_the_html_are_uncovered_but_real_ones_are_not(self):
        doc, _, report = self.doc()
        self.assertEqual(report["uncovered"], 0)
        bad = doc.replace("</body>", "<p>About .5% and 1,000.</p></body>")
        self.assertTrue(uncovered_in_html(bad, {"26", "105"}))
        self.assertEqual(uncovered_in_html(doc, {"26", "105"}), [])

    def test_html_id_cell_not_on_the_batch_list_is_caught(self):
        doc, _, report = self.doc()
        bad = doc.replace('<td class="id">26</td>', '<td class="id">99</td>')
        self.assertNotEqual(bad, doc)
        self.assertEqual(len(visible_numbers(bad, {"26", "105"})), report["numbers"] + 1)
        self.assertTrue(any(u.startswith("uncovered:99") for u in uncovered_in_html(bad, {"26", "105"})))

    def test_a_rejected_section_is_left_out_and_listed(self):
        f, fl = facts56()
        del f["limit"]
        item = {"part": "3.2.P.5.6", "task_id": "t1", "attribute": "Dissolution", "batch_ids": [],
                "sections": build_p56(TASK56, f, fl, TEXT56)}
        doc, records, report = build_document([item])
        self.assertEqual(records, [])
        self.assertEqual(report["missing"], 1)
        self.assertNotIn('data-section="justification"', doc)


class ToolTests(unittest.TestCase):
    def test_tool_writes_three_files_and_numbers_equal_placements(self):
        from tools import render_doc
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(render_doc.main(["--out", tmp]), 0)
            files = {p.name for p in Path(tmp).iterdir()}
            self.assertEqual(files, {"P5.html", "placements.jsonl", "report.txt"})
            report = (Path(tmp) / "report.txt").read_text(encoding="utf-8")
            self.assertIn("missing 0", report)
            self.assertIn("uncovered 0", report)
            html_text = (Path(tmp) / "P5.html").read_text(encoding="utf-8")
            self.assertNotRegex(html_text, r"(?i)\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) batch")
            self.assertIn("numbers == placements", report)
            rows = [json.loads(x) for x in (Path(tmp) / "placements.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertTrue(rows)


if __name__ == "__main__":
    unittest.main()
