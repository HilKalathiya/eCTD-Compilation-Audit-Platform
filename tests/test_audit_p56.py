"""Tests for tools/audit_p56.py with the fake model only: counts add up, planted rows are in the blind sheet and hidden, a human who misses a planted row fails.

    python -m unittest tests.test_audit_p56
"""
import csv
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import audit_p56 as ap  # noqa: E402
import writer_run as wr  # noqa: E402
from ectd_engine.loaders import lek  # noqa: E402
from ectd_engine.validator.spec import verify_render  # noqa: E402
from ectd_engine.writer.spec_facts import compute_spec_facts, render_paragraph  # noqa: E402
from ectd_engine.writer.spec_loop import SpecMockClient, run_spec_task  # noqa: E402
from tests.test_batch_writer import make_store  # noqa: E402

COL_Q, COL_D = "impurity_o", "dissolution_av"
MDD = Decimal("40")
BATCHES = [str(i) for i in range(1, 61)]


def values_for(col):
    """60 batches; every 7th is quarantined (no fact); one q3b value sits above its limit so n_outside can be above 0."""
    out = {}
    for i, b in enumerate(BATCHES):
        if i % 7 == 6:
            out[b] = None
        elif col == COL_Q:
            out[b] = "0.60" if i == 3 else f"0.{(i % 40) + 10:02d}"
        else:
            out[b] = f"{85 + (i % 15)}.5"
    return out


def build():
    g1, known = make_store(values_for(COL_Q), COL_Q)
    g2, _ = make_store(values_for(COL_D), COL_D)

    def get(fid):
        return g1(fid) or g2(fid)
    live = {COL_Q: SimpleNamespace(test=lek.COLUMNS[COL_Q][0], limit_kind="NMT", limit=Decimal("0.5"), unit="%",
                                   basis="q3b_qualification", quote="Impurities above the thresholds need justification",
                                   page=11, doc_version="v1"),
            COL_D: SimpleNamespace(test=lek.COLUMNS[COL_D][0], limit_kind="NLT", limit=Decimal("80"), unit="%",
                                   basis="declared", quote=None, page=None, doc_version=None)}
    return get, known, live


class BadClient:
    """Always overclaims, so the paragraph is rejected."""

    def chat(self, messages, temperature, seed, context=None, schema=None):
        return {"text": "The limit is in line with ICH guidance. The product is safe.", "seconds": 0, "output_tokens": 9}


def make_run(count=40, n_bad=4):
    get, known, live = build()
    windows = wr.make_p56_windows(get, known, live, MDD, count)
    tasks, results = {}, []
    for i, t in enumerate(windows):
        res = run_spec_task(BadClient() if i >= count - n_bad else SpecMockClient(), t)
        tasks[t["task_id"]] = t
        results.append(json.loads(json.dumps({"task_id": t["task_id"], "accepted": res["accepted"], "rendered": res["rendered"],
                                              "flags": {"n_excluded": t["n_excluded"]}, "drafts": res["drafts"]})))

    def expect(task, get_fact=get, known_batches=known):
        return ap.expected_task(task, get_fact, known_batches, live[task["column"]], MDD)
    return tasks, results, expect, get, known, live


class AuditTests(unittest.TestCase):
    def test_counts_add_up(self):
        tasks, results, expect, *_ = make_run(40, 4)
        rows, s = ap.audit(tasks, results, expect)
        self.assertEqual((s["total"], s["accepted"], s["rejected"], s["wrong"]), (40, 36, 4, 0))
        self.assertEqual(s["accepted"] + s["rejected"], len(rows))
        self.assertEqual(sum(1 for r in rows if r["reread"] == "right"), 36)
        self.assertEqual(s["drafts_accepted"], 72)  # fake model: 2 drafts per accepted paragraph
        self.assertEqual(s["drafts_all"], 72 + 16)  # 4 drafts for each rejected one
        self.assertGreater(s["with_excluded"], 0)

    def test_windows_leave_quarantined_batches_out(self):
        tasks, *_ = make_run(40, 0)
        self.assertTrue(any(t["n_excluded"] and t["n"] == len(t["batches"]) - t["n_excluded"] for t in tasks.values()))
        self.assertTrue(any(t["n_outside"] for t in tasks.values()))  # the planted 0.60 value is counted outside

    def test_rejects_listed_by_rule_with_the_sentence(self):
        tasks, results, expect, *_ = make_run(10, 10)
        rows, s = ap.audit(tasks, results, expect)
        self.assertEqual(s["accepted"], 0)
        self.assertTrue(s["final_rules"])
        rule = next(iter(s["final_rules"]))
        self.assertTrue(s["examples"][rule][0][1])

    def test_changed_limit_in_finished_text_is_wrong(self):
        tasks, results, expect, *_ = make_run(10, 0)
        i = next(k for k, r in enumerate(results) if "not more than 0.5%" in r["rendered"])
        results[i]["rendered"] = results[i]["rendered"].replace("not more than 0.5%", "not more than 0.6%")
        rows, s = ap.audit(tasks, results, expect)
        self.assertEqual(s["wrong"], 1)
        self.assertEqual(rows[i]["reread"], "wrong")

    def test_changed_stored_fact_is_wrong(self):
        tasks, results, _, get, known, live = make_run(10, 0)
        get2, known2 = make_store(dict(values_for(COL_Q), **{"1": "0.55"}), COL_Q)  # batch 1 now outside the limit
        g3, _ = make_store(values_for(COL_D), COL_D)
        rows, s = ap.audit(tasks, results, lambda t: ap.expected_task(t, lambda f: get2(f) or g3(f), known2, live[t["column"]], MDD))
        self.assertGreater(s["wrong"], 0)

    def test_unknown_batch_stops(self):
        tasks, results, _, get, _, live = make_run(10, 0)
        with self.assertRaises(ap.AuditError):
            ap.audit(tasks, results, lambda t: ap.expected_task(t, get, set(), live[t["column"]], MDD))


class BlindSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tasks, self.results, self.expect, *_ = make_run(40, 4)
        self.rows, self.s = ap.audit(self.tasks, self.results, self.expect)
        ap.write_outputs(self.tmp.name, self.rows, self.s, self.results, self.tasks, self.expect)
        self.blind = Path(self.tmp.name) / "blind.csv"

    def read(self, name="blind.csv"):
        with open(Path(self.tmp.name) / name, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def fill(self, label_for):
        sheet, key = self.read(), {r["blind_id"]: r for r in self.read("blind_key.csv")}
        with open(self.blind, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(sheet[0]))
            w.writeheader()
            for r in sheet:
                r["hil_label"] = label_for(r["blind_id"], key[r["blind_id"]])
                w.writerow(r)

    def test_sheet_has_25_rows_with_3_planted_hidden(self):
        sheet, key = self.read(), self.read("blind_key.csv")
        self.assertEqual(len(sheet), 25)
        self.assertEqual(list(sheet[0]), ["blind_id", "attribute", "facts", "text", "hil_label"])
        self.assertTrue(all(r["hil_label"] == "" for r in sheet))
        planted = [k for k in key if k["planted"]]
        self.assertEqual(sorted(k["planted"] for k in planted), sorted(ap.PLANTED))
        self.assertEqual(len({k["task_id"] for k in key}), 25)
        text = self.blind.read_text(encoding="utf-8").lower()
        for word in ("planted", "reread", "re-read"):
            self.assertNotIn(word, text)
        self.assertNotEqual([k["blind_id"] for k in planted], ["B01", "B02", "B03"])  # shuffled, not first

    def test_planted_rows_really_are_wrong_and_real_rows_are_right(self):
        sheet, key = self.read(), {r["blind_id"]: r for r in self.read("blind_key.csv")}
        for r in sheet:
            k = key[r["blind_id"]]
            problems = verify_render(r["text"], self.expect(self.tasks[k["task_id"]]))
            self.assertEqual(bool(problems), bool(k["planted"]), r["blind_id"])

    def test_plant_that_changes_nothing_is_an_error(self):
        exp = self.expect(next(t for t in self.tasks.values() if t["basis"] == "q3b_qualification"))
        with self.assertRaises(ap.AuditError):
            ap.plant(ap.PLANTED[0], "Nothing to change here.", exp)

    def test_every_tamper_kind_is_made_and_caught_for_small_and_large_counts(self):  # T-051: counts are digits ("9 batches")
        base = next(t for t in self.tasks.values() if t["basis"] == "declared" and not t["n_outside"])
        for n in (1, 2, 9, 12, 60):
            task = dict(base, n=n)
            facts = compute_spec_facts(task)[0]
            text = render_paragraph("The acceptance criterion for X is [[limit_kind]] [[limit]], which is [[basis]]. Results for [[n_batches]] "
                                    "ranged from [[min_value]] to [[max_value]]. No result was outside the limit.", facts, task["basis"])
            self.assertEqual(verify_render(text, task), [], n)
            for kind in ap.PLANTED:
                bad = ap.plant(kind, text, task)
                self.assertNotEqual(bad, text, (kind, n))
                self.assertTrue(verify_render(bad, task), (kind, n))
        tampered = ap.plant(ap.PLANTED[2], text, task)
        self.assertIn("61 batches", tampered)
        self.assertNotIn("60 batches", tampered)

    def test_count_tamper_on_an_old_word_count_is_refused(self):  # planted: a paragraph that still spells the count out is not tampered silently
        task = next(t for t in self.tasks.values() if t["basis"] == "declared")
        words = "Results for nine batches ranged widely."
        with self.assertRaises(ap.AuditError):
            ap.plant(ap.PLANTED[2], words, dict(task, n=9))

    def test_expected_task_asks_for_only_the_dose_row(self):
        get, known, live = build()
        row = "10 mg - 100 mg 0.5% or 200 µg TDI, whichever is lower"
        j = live[COL_Q]
        j.quote = "Qualification Thresholds Maximum Daily Dose1 Threshold2,3 < 10 mg 1.0% or 50 µg TDI, whichever is lower " + row
        task = next(t for t in wr.make_p56_windows(get, known, live, MDD, 4) if t["basis"] == "q3b_qualification")
        exp = ap.expected_task(task, get, known, j, MDD)
        self.assertEqual(exp["q3b_quote"], row)

    def test_missing_labels_give_a_clear_error(self):
        with self.assertRaises(ap.AuditError) as cm:
            ap.score(self.tmp.name, self.rows)
        self.assertIn("hil_label", str(cm.exception))
        self.fill(lambda b, k: "" if b == "B05" else "right")
        with self.assertRaises(ap.AuditError):
            ap.score(self.tmp.name, self.rows)
        self.fill(lambda b, k: "maybe")
        with self.assertRaises(ap.AuditError):
            ap.score(self.tmp.name, self.rows)

    def test_catching_all_three_and_agreeing_passes(self):
        self.fill(lambda b, k: "wrong" if k["planted"] else "right")
        sc = ap.score(self.tmp.name, self.rows)
        self.assertTrue(sc["pass"])
        self.assertEqual((sc["planted"], sc["missed"], sc["differ"]), (3, [], []))

    def test_hil_labelling_everything_right_fails(self):
        self.fill(lambda b, k: "right")
        sc = ap.score(self.tmp.name, self.rows)
        self.assertFalse(sc["pass"])
        self.assertEqual(len(sc["missed"]), 3)

    def test_hil_missing_one_planted_row_fails(self):
        first = [k for k in self.read("blind_key.csv") if k["planted"]][0]["blind_id"]
        self.fill(lambda b, k: "wrong" if (k["planted"] and b != first) else "right")
        sc = ap.score(self.tmp.name, self.rows)
        self.assertFalse(sc["pass"])
        self.assertEqual([m[0] for m in sc["missed"]], [first])

    def test_hil_catching_all_but_flagging_a_real_row_fails(self):
        real = next(k for k in self.read("blind_key.csv") if not k["planted"])["blind_id"]
        self.fill(lambda b, k: "wrong" if (k["planted"] or b == real) else "right")
        sc = ap.score(self.tmp.name, self.rows)
        self.assertFalse(sc["pass"])
        self.assertEqual([d[0] for d in sc["differ"]], [real])

    def test_too_few_accepted_stops(self):
        tasks, results, expect, *_ = make_run(20, 0)
        rows, s = ap.audit(tasks, results, expect)
        with self.assertRaises(ap.AuditError):
            ap.write_outputs(self.tmp.name, rows, s, results[:20], tasks, expect) if len(results) < 25 else self.fail("setup")


if __name__ == "__main__":
    unittest.main()
