"""Tests for tools/audit_p54.py with the fake model only: counts add up, a wrong section is labelled wrong, missing blind labels stop the run.

    python -m unittest tests.test_audit_p54
"""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import audit_p54 as ap  # noqa: E402
from ectd_engine.writer.batch_loop import BatchMockClient, run_batch_task  # noqa: E402
from tests.test_batch_writer import make_store, make_task  # noqa: E402

VALUES = {"1": "0.10", "2": "0.20", "3": "0.35", "4": None}


class BadClient:
    """Always breaks the compliance rule, so the section is rejected."""

    def chat(self, messages, temperature, seed, context=None, schema=None):
        return {"text": "All batches met the specification and the results were acceptable.", "seconds": 0, "output_tokens": 9}


def one(task_id, client, values=VALUES):
    get, known = make_store(values)
    task = dict(make_task(list(values)), task_id=task_id)
    res = run_batch_task(client, task, get, known)
    saved = {"task_id": task_id, "accepted": res["accepted"], "rendered": res["rendered"], "table": res["table"],
             "flags": {"n_excluded": res["flags"]["n_excluded"]}, "drafts": res["drafts"]}
    return task, json.loads(json.dumps(saved)), get, known


def many(n_good, n_bad):
    tasks, results = {}, []
    for i in range(n_good + n_bad):
        client = BatchMockClient() if i < n_good else BadClient()
        t, r, get, known = one(f"t{i}", client)
        tasks[t["task_id"]], _ = t, results.append(r)
    return tasks, results, get, known


class AuditTests(unittest.TestCase):
    def test_counts_add_up(self):
        tasks, results, get, known = many(7, 3)
        rows, s = ap.audit(tasks, results, get, known)
        self.assertEqual((s["total"], s["accepted"], s["rejected"], s["wrong"]), (10, 7, 3, 0))
        self.assertEqual(s["accepted"] + s["rejected"], len(rows))
        self.assertEqual(sum(1 for r in rows if r["reread"] == "right"), 7)
        self.assertEqual(s["with_excluded"], 10)
        self.assertEqual(s["drafts_accepted"], 14)  # fake model: 2 drafts per accepted section
        self.assertEqual(s["drafts_all"], 14 + 12)  # 4 drafts for each rejected section
        self.assertEqual(s["first_try"], 0)

    def test_rejects_listed_by_rule_with_the_sentence(self):
        tasks, results, get, known = many(0, 2)
        rows, s = ap.audit(tasks, results, get, known)
        self.assertTrue(s["final_rules"])
        rule = next(iter(s["final_rules"]))
        self.assertIn("compliance", " ".join(s["final_rules"]))
        self.assertEqual(s["final_rules"][rule], 2)
        self.assertIn("met", s["examples"][rule][0][1])

    def test_planted_wrong_section_is_labelled_wrong(self):
        tasks, results, get, known = many(3, 0)
        r = results[1]
        self.assertIn("0.10", r["rendered"])
        r["rendered"] = r["rendered"].replace("0.10", "0.11")  # a changed number in the finished text
        rows, s = ap.audit(tasks, results, get, known)
        self.assertEqual(s["wrong"], 1)
        self.assertEqual([x["reread"] for x in rows], ["right", "wrong", "right"])

    def test_planted_changed_fact_is_labelled_wrong(self):
        tasks, results, get, known = many(1, 0)
        get2, known2 = make_store(dict(VALUES, **{"3": "0.36"}))  # the store no longer matches what was written
        rows, s = ap.audit(tasks, results, get2, known2)
        self.assertEqual(s["wrong"], 1)

    def test_unknown_batch_stops(self):
        tasks, results, get, known = many(1, 0)
        with self.assertRaises(ap.AuditError):
            ap.audit(tasks, results, get, set())

    def test_rule_of_groups_details_together(self):
        self.assertEqual(ap.rule_of("compliance or specification wording ('met'), but no spec"),
                         ap.rule_of("compliance or specification wording ('pass'), but no spec"))
        self.assertEqual(ap.rule_of("needs 2-5 sentences, got 7"), ap.rule_of("needs 2-5 sentences, got 1"))


class BlindSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tasks, self.results, self.get, self.known = many(30, 2)
        self.rows, self.s = ap.audit(self.tasks, self.results, self.get, self.known)
        ap.write_outputs(self.tmp.name, self.rows, self.s, self.results, self.tasks)
        self.blind = Path(self.tmp.name) / "blind.csv"

    def read(self):
        with open(self.blind, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def fill(self, label_for):
        sheet = self.read()
        with open(self.blind, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(sheet[0]))
            w.writeheader()
            for i, r in enumerate(sheet):
                r["hil_label"] = label_for(i)
                w.writerow(r)

    def test_sheet_has_25_rows_without_verdicts(self):
        sheet = self.read()
        self.assertEqual(len(sheet), 25)
        self.assertEqual(list(sheet[0]), ["blind_id", "attribute", "facts", "text", "hil_label"])
        self.assertTrue(all(r["hil_label"] == "" for r in sheet))
        self.assertNotIn("reread", self.blind.read_text(encoding="utf-8").lower())
        self.assertEqual(len({r["text"] for r in sheet}) >= 1, True)

    def test_missing_labels_give_a_clear_error_not_zero_wrong(self):
        with self.assertRaises(ap.AuditError) as cm:
            ap.score(self.tmp.name, self.rows)
        self.assertIn("hil_label", str(cm.exception))
        self.fill(lambda i: "right" if i < 24 else "")  # one still empty
        with self.assertRaises(ap.AuditError):
            ap.score(self.tmp.name, self.rows)
        self.fill(lambda i: "maybe")
        with self.assertRaises(ap.AuditError):
            ap.score(self.tmp.name, self.rows)

    def test_all_right_agrees(self):
        self.fill(lambda i: "right")
        sc = ap.score(self.tmp.name, self.rows)
        self.assertEqual((sc["n"], sc["hil_wrong"], sc["differ"]), (25, [], []))

    def test_hil_wrong_label_is_reported(self):
        self.fill(lambda i: "wrong" if i == 3 else "right")
        sc = ap.score(self.tmp.name, self.rows)
        self.assertEqual(sc["hil_wrong"], ["B04"])
        self.assertEqual(len(sc["differ"]), 1)

    def test_missing_sheet_is_an_error(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(ap.AuditError):
                ap.score(empty, self.rows)

    def test_missing_run_files_are_an_error(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(ap.AuditError):
                ap.load_run(empty)


if __name__ == "__main__":
    unittest.main()
