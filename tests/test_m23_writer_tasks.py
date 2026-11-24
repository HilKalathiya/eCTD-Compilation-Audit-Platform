"""Tests for the 2.3 task files and prompt: tasks regenerate to the saved bytes and hashes, and the prompt never carries a digit or a value."""
import hashlib
import re
import unittest
from pathlib import Path

from ectd_engine.summary import m23_loop as L
from ectd_engine.summary import m23_prompt as MP
from ectd_engine.summary import m23_tasks as T

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evidence" / "T-071" / "tasks"


class TaskFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all = T.all_tasks()

    def test_counts_and_flags(self):
        self.assertEqual((len(self.all["real"]), len(self.all["dev"]), len(self.all["heldout"])), (1, 10, 20))
        self.assertFalse(self.all["real"][0]["synthetic"])
        self.assertTrue(all(t["synthetic"] for t in self.all["dev"] + self.all["heldout"]))
        ids = [t["task_id"] for ts in self.all.values() for t in ts]
        self.assertEqual(len(ids), len(set(ids)))

    def test_synthetic_tasks_are_marked_everywhere(self):
        for t in self.all["dev"] + self.all["heldout"]:
            self.assertIn("synthetic test case", t["title"])
            self.assertTrue(all("SYNTHETIC" in r["definition"] for r in t["graph_rows"].values()), t["task_id"])
        self.assertNotIn("synthetic", self.all["real"][0]["title"])

    def test_saved_task_files_equal_what_the_code_makes_now(self):
        for which, tasks in self.all.items():
            for t in tasks:
                saved = (TASKS / which / (t["task_id"] + ".json")).read_bytes()
                self.assertEqual(saved, T.task_json(t), t["task_id"])

    def test_the_hash_list_matches_the_files(self):
        lines = (TASKS / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 31)
        for line in lines:
            digest, name = line.split("  ")
            self.assertEqual(hashlib.sha256((TASKS / name).read_bytes()).hexdigest(), digest, name)

    def test_the_held_out_hashes_in_state_md_match_the_files(self):
        # T-074 moved the T-071..T-073 history, text unchanged, to evidence/T-074/history.md; the hashes are searched in both files
        state = (ROOT / "STATE.md").read_text(encoding="utf-8") + (ROOT / "evidence" / "T-074" / "history.md").read_text(encoding="utf-8")
        for t in self.all["heldout"]:
            self.assertIn(f"{T.sha256(t)}  {t['task_id']}", state, t["task_id"])

    def test_dev_and_heldout_do_not_share_numbers_with_each_other_or_with_the_real_task(self):
        def sig(t):
            return (tuple(s["value"] for s in t["spec"]), tuple(s["value"] for s in t["public"].values()),
                    tuple((g["low"]["value"], g["high"]["value"]) for g in t["results"]))
        sigs = [sig(t) for t in self.all["dev"] + self.all["heldout"] + self.all["real"]]
        self.assertEqual(len(sigs), len(set(sigs)))

    def test_some_tasks_hold_the_same_number_in_two_places(self):
        same = [t["task_id"] for t in self.all["dev"] + self.all["heldout"] if t["public"]["shelf"]["value"] == t["public"]["long"]["value"]]
        self.assertGreaterEqual(len([s for s in same if "dev" in s]), 1)
        self.assertGreaterEqual(len([s for s in same if "held" in s]), 1)


class PromptHasNoNumbers(unittest.TestCase):
    def test_no_digit_in_any_message_of_any_task_unit(self):
        for ts in T.all_tasks().values():
            for t in ts:
                for u in T.units_of(t):
                    for m in MP.build_messages(T.view_of(u)):
                        self.assertNotRegex(m["content"], r"\d", (t["task_id"], u["unit_id"]))

    def test_no_value_of_a_task_appears_in_its_messages(self):
        t = T.real_task()
        for u in T.units_of(t):
            text = " ".join(m["content"] for m in MP.build_messages(T.view_of(u)))
            for s in u["slots"].values():
                self.assertNotIn(s["text"], text)
                self.assertNotIn(s["fact_id"], text)

    def test_feedback_turns_carry_no_digit(self):
        u = T.units_of(T.real_task())[0]
        draft = "Colour: NMT 5 and 36 months"
        msgs = MP.build_messages(T.view_of(u), [(L._clean(draft), [L._clean("(a) the draft writes a digit in 36 months")])])
        self.assertEqual(len(msgs), 6)
        self.assertNotRegex(" ".join(m["content"] for m in msgs), r"\d")

    def test_the_prompt_builder_refuses_a_digit(self):
        u = T.units_of(T.real_task())[0]
        with self.assertRaises(ValueError):
            MP.build_messages(T.view_of(u), [("36 months", ["x"])])

    def test_slot_names_and_labels_are_digit_free(self):
        for u in T.units_of(T.real_task()):
            for name, label in T.view_of(u)["slots"].items():
                self.assertNotRegex(name + label, r"\d")


if __name__ == "__main__":
    unittest.main()
