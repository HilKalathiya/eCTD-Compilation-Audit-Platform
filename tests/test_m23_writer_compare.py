"""Tests for the independent 2.3 comparison (saved HTML vs task facts): it passes a correct document and fails each planted wrong number or wording."""
import tempfile
import unittest
from pathlib import Path

from ectd_engine.summary import m23_compare as C
from ectd_engine.summary import m23_loop as L
from ectd_engine.summary import m23_tasks as T
from tests.test_m23_writer import Scripted, stub_messages


class Compare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.task = T.synthetic_task("dev", 3)
        cls.out = Path(cls.tmp.name) / "w"
        res = L.run_world(Scripted(cls.task), cls.task, cls.out, build_messages=stub_messages)
        assert res["accepted"], res
        cls.html = (cls.out / "render_1" / "M23.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check_text(self, html):
        p = Path(self.tmp.name) / "variant.html"
        p.write_text(html, encoding="utf-8")
        return C.compare(p, self.task)

    def test_a_correct_document_passes(self):
        res = C.compare(self.out / "render_1" / "M23.html", self.task)
        self.assertTrue(res["ok"], res)
        self.assertGreater(res["numbers"], 10)

    def test_real_task_document_passes(self):
        task = T.real_task()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        res = L.run_world(Scripted(task), task, Path(tmp.name) / "w", build_messages=stub_messages)
        self.assertTrue(res["accepted"])
        self.assertTrue(C.compare(Path(tmp.name) / "w" / "render_1" / "M23.html", task)["ok"])

    def test_one_wrong_number_fails(self):
        shelf = self.task["public"]["shelf"]["value"]
        bad = self.html.replace(f">{shelf}</span> months when stored", f">{int(shelf) + 1}</span> months when stored", 1)
        self.assertNotEqual(bad, self.html)
        res = self.check_text(bad)
        self.assertFalse(res["ok"])
        self.assertTrue(any("numbers differ" in p for p in res["problems"]))

    def test_two_numbers_swapped_fails_even_if_each_is_a_real_fact(self):
        g = self.task["results"][0]
        lo, hi = g["low"]["value"], g["high"]["value"]
        self.assertNotEqual(lo, hi, "the task data must give this group two different values")
        bad = self.html.replace(f">{lo}</span>", ">@@</span>", 1).replace(f">{hi}</span>", f">{lo}</span>", 1).replace(">@@</span>", f">{hi}</span>", 1)
        self.assertNotEqual(bad, self.html)
        self.assertFalse(self.check_text(bad)["ok"])

    def test_a_changed_word_fails(self):
        self.assertFalse(self.check_text(self.html.replace("ranged from", "stayed from", 1))["ok"])

    def test_a_dropped_demo_label_fails(self):
        self.assertFalse(self.check_text(self.html.replace("In illustrative demonstration data, ", "", 1))["ok"])

    def test_a_missing_paragraph_fails(self):
        start = self.html.index('<p data-section="results">')
        end = self.html.index("</p>", start) + 4
        self.assertFalse(self.check_text(self.html[:start] + self.html[end:])["ok"])

    def test_synthetic_marking_must_agree(self):
        self.assertFalse(self.check_text(self.html.replace(" (synthetic test case)", ""))["ok"])


if __name__ == "__main__":
    unittest.main()
