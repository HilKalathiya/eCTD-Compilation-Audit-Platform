"""Tests for the independent T-072 comparison: it passes a correct document and fails each planted wrong number, place, label, claim or missing paragraph."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.summary import m23_compare2 as C
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import m23_loop2 as L
from ectd_engine.summary import m23_tasks2 as T
from tests.test_m23_v2_writer import FakeGraph, Scripted, stub_messages


def render(task, rows, graph, **kw):
    tmp = tempfile.TemporaryDirectory()
    out = Path(tmp.name) / "w"
    res = L.run_world(Scripted(task, rows, **kw), task, out, graph, build_messages=stub_messages)
    assert res["accepted"], res
    return tmp, out, (out / "render_1" / "M23.html").read_text(encoding="utf-8")


class Compare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for i in range(1, T.DEV_COUNT + 1):                          # a task with a timed attribute, an outside-limit group and a clean group
            task, rows = T.synthetic_task("dev", i)
            units = [u for u in T.units_of(task, rows) if u["kind"] == "result"]
            if any(u["has_tp"] for u in units) and any(u["outside"] for u in units) and any(not u["outside"] for u in units):
                cls.task, cls.rows = task, rows
                break
        else:
            raise AssertionError("no suitable dev task")
        cls.tmp, cls.out, cls.html = render(cls.task, cls.rows, MG.MemoryGraph(cls.rows))
        cls.units = T.units_of(cls.task, cls.rows)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, html, rows=None):
        p = Path(self.tmp.name) / "variant.html"
        p.write_text(html, encoding="utf-8")
        return C.compare(p, self.task, rows or self.rows)

    def test_a_correct_document_passes_in_every_wording(self):
        self.assertTrue(C.compare(self.out / "render_1" / "M23.html", self.task, self.rows)["ok"])
        for k in range(1, 5):
            tmp, out, html = render(self.task, self.rows, MG.MemoryGraph(self.rows), choice={kind: k for kind in ("shelf", "excursion", "study", "spec_intro", "spec_row", "range", "claim")})
            self.addCleanup(tmp.cleanup)
            res = C.compare(out / "render_1" / "M23.html", self.task, self.rows)
            self.assertTrue(res["ok"], (k, res))

    def test_the_real_document_passes(self):
        rows, task = G.collect(), T.real_task()
        tmp, out, html = render(task, rows, FakeGraph(rows))
        self.addCleanup(tmp.cleanup)
        res = C.compare(out / "render_1" / "M23.html", task, rows)
        self.assertTrue(res["ok"], res)
        self.assertGreater(res["numbers"], 30)

    def test_one_wrong_number_fails(self):
        shelf = self.rows[self.task["public"]["shelf"]["fact_id"]]["value_text"]
        bad = self.html.replace(f">{shelf}</span> months", f">{int(shelf) + 1}</span> months", 1)
        self.assertNotEqual(bad, self.html)
        self.assertFalse(self.check(bad)["ok"])

    def test_a_graph_that_changed_since_rendering_is_noticed(self):
        changed = copy.deepcopy(self.rows)
        sid = self.task["public"]["shelf"]["fact_id"]
        changed[sid]["value_text"] = str(int(changed[sid]["value_text"]) + 1)
        self.assertFalse(self.check(self.html, changed)["ok"])

    def test_two_numbers_in_the_wrong_places_fail_even_when_each_is_a_real_fact(self):
        g = self.task["results"][0]
        a, b = g["stat"]["min"], g["stat"]["max"]
        bad = self.html
        la, lb = f'data-src="{a}"', f'data-src="{b}"'
        bad = bad.replace(la, "@@", 1).replace(lb, la, 1).replace("@@", lb, 1)
        self.assertNotEqual(bad, self.html)
        self.assertFalse(self.check(bad)["ok"])

    def test_equal_values_in_different_places_cannot_trade_ids(self):
        task, rows = T.synthetic_task("dev", 4)                       # shelf life = long-term months
        tmp, out, html = render(task, rows, MG.MemoryGraph(rows))
        self.addCleanup(tmp.cleanup)
        a, b = task["public"]["shelf"]["fact_id"], task["public"]["long"]["fact_id"]
        bad = html.replace(f'data-src="{a}"', "@@", 1).replace(f'data-src="{b}"', f'data-src="{a}"', 1).replace("@@", f'data-src="{b}"', 1)
        p = Path(tmp.name) / "bad.html"
        p.write_text(bad, encoding="utf-8")
        self.assertNotEqual(bad, html)
        self.assertFalse(C.compare(p, task, rows)["ok"])

    def test_a_dropped_demo_label_fails(self):
        self.assertFalse(self.check(self.html.replace("In illustrative demonstration data, ", "", 1))["ok"])

    def test_a_demo_label_on_the_public_paragraph_fails(self):
        bad = self.html.replace('<p data-section="public">', '<p data-section="public">In illustrative demonstration data, ', 1)
        self.assertFalse(self.check(bad)["ok"])

    def test_a_missing_paragraph_fails(self):
        start = self.html.index('<p data-section="results">')
        end = self.html.index("</p>", start) + 4
        self.assertFalse(self.check(self.html[:start] + self.html[end:])["ok"])

    def test_a_loose_digit_fails(self):
        self.assertFalse(self.check(self.html.replace("conditions", "conditions in 7 batches", 1))["ok"])

    def test_the_synthetic_marking_must_agree(self):
        self.assertFalse(self.check(self.html.replace(" (synthetic test case)", ""))["ok"])

    def test_a_claim_that_disagrees_with_the_graph_count_fails_in_both_directions(self):
        none_unit = next(u for u in self.units if u["kind"] == "result" and u["outside"] == 0)
        some_unit = next(u for u in self.units if u["kind"] == "result" and u["outside"] > 0)
        html = self.html
        self.assertIn("had results outside the limit", html)
        # the outside group is made to say "none outside": the compare must refuse it
        bad = html.replace("had results outside the limit", "had no results outside the limit", 1)
        res = self.check(bad)
        self.assertFalse(res["ok"])
        self.assertTrue(any("disagrees with the graph" in p for p in res["problems"]), res["problems"])
        # and a clean group is made to say "some outside"
        sentence = next(s for s in ("had no results outside the limit", "was within the specification limits", "was outside the limit") if s in html)
        bad2 = html.replace(sentence, "had results outside the limit", 1)
        res2 = self.check(bad2)
        self.assertFalse(res2["ok"])
        self.assertTrue(any("disagrees with the graph" in p for p in res2["problems"]), res2["problems"])
        self.assertTrue(none_unit and some_unit)


if __name__ == "__main__":
    unittest.main()
