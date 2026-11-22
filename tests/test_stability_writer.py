"""Tests the P.8.3 writer: placeholder checks, retry feedback, the independent CSV re-read; every check has a planted error that makes it fail."""
import json
import tempfile
import unittest
from pathlib import Path

from ectd_engine.stability import facts as F, loop, reread
from ectd_engine.stability.prompt import build_messages
from ectd_engine.stability.runner import run_p83

P83 = F.p83_facts(F.load_rows())
TASKS = {t["task_id"]: t for t in loop.make_tasks(P83)}
PUBLIC = TASKS["p83_public"]
DEMO = TASKS["demo_25C-60-RH_Assay"]
ROWS = reread.read_rows(F.DEFAULT_CSV)
GOOD_PUBLIC, GOOD_DEMO = loop.mock_text(PUBLIC), loop.mock_text(DEMO)


def problems(text, task):
    return loop.draft_problems(text, task)[0]


class Tasks(unittest.TestCase):
    def test_one_public_task_and_one_per_group(self):
        self.assertEqual(len(TASKS), 1 + len(P83["demo"]))
        self.assertEqual(len(TASKS), 10)

    def test_values_are_made_by_code(self):
        self.assertEqual(PUBLIC["slots"]["storage_low"]["value"], "20°C")
        self.assertEqual(PUBLIC["slots"]["shelf_life_months"]["value"], "36")


class CleanDrafts(unittest.TestCase):
    def test_good_drafts_pass_and_render_numbers(self):
        self.assertEqual(problems(GOOD_PUBLIC, PUBLIC), [])
        text = loop.draft_problems(GOOD_PUBLIC, PUBLIC)[1]
        self.assertIn("The proposed shelf life is 36 months when stored at 20°C to 25°C.", text)
        self.assertEqual(problems(GOOD_DEMO, DEMO), [])
        self.assertTrue(loop.draft_problems(GOOD_DEMO, DEMO)[1].startswith("In illustrative demonstration data, Assay at 25C/60%RH"))

    def test_every_task_has_a_passing_mock_draft(self):
        for t in TASKS.values():
            self.assertEqual(problems(loop.mock_text(t), t), [], t["task_id"])


class PlantedDraftErrors(unittest.TestCase):
    def assertRejected(self, text, task, needle):
        got = problems(text, task)
        self.assertTrue(any(needle in p for p in got), (needle, got))
        self.assertIsNone(loop.draft_problems(text, task)[1])

    def test_digit_written_by_the_model(self):
        self.assertRejected(GOOD_PUBLIC.replace("[[shelf_life_months]]", "36"), PUBLIC, "writes a digit")

    def test_number_word(self):
        self.assertRejected(GOOD_PUBLIC.replace("[[shelf_life_months]] months", "thirty months"), PUBLIC, "number word")

    def test_degree_sign_typed_by_the_model(self):
        self.assertRejected(GOOD_PUBLIC.replace("to [[storage_high]].", "to [[storage_high]]°."), PUBLIC, "degree sign")

    def test_unknown_placeholder(self):
        self.assertRejected(GOOD_DEMO.replace("[[min]]", "[[mean]]"), DEMO, "not in the FACTS list")

    def test_missing_required_placeholder(self):
        self.assertRejected(GOOD_PUBLIC.replace(" and [[accel_months]] months at accelerated conditions", ""), PUBLIC,
                            "missing placeholder [[accel_months]]")

    def test_swapped_slots_fail_the_validator(self):
        self.assertRejected(GOOD_DEMO.replace("from [[min]] to [[max]]", "from [[max]] to [[min]]"), DEMO, "unsupported")

    def test_wrong_slot_in_a_public_sentence(self):
        bad = GOOD_PUBLIC.replace("from [[excursion_low]] to [[excursion_high]]", "from [[excursion_high]] to [[excursion_low]]")
        self.assertRejected(bad, PUBLIC, "unsupported")

    def test_missing_demo_label(self):
        self.assertRejected(GOOD_DEMO.replace("In illustrative demonstration data, [[attribute]] at [[condition]] ranged",
                                              "[[attribute]] at [[condition]] ranged"), DEMO, "demo_unlabelled")

    def test_demo_label_on_a_public_sentence(self):
        bad = GOOD_PUBLIC.replace("Stability was demonstrated", "In illustrative demonstration data, stability was demonstrated")
        self.assertRejected(bad, PUBLIC, "copy the matching example sentence exactly")

    def test_made_up_sentence(self):
        self.assertRejected(GOOD_DEMO + " The product is stable.", DEMO, "unrecognised")

    def test_sentence_form_repeated(self):
        self.assertRejected(GOOD_DEMO + " " + GOOD_DEMO.split(". ")[0] + ".", DEMO, "exactly these sentence forms")

    def test_empty_draft(self):
        self.assertEqual(problems("", DEMO), ["empty output"])


class Feedback(unittest.TestCase):
    def test_retry_messages_carry_draft_and_problems(self):
        fb = [("bad draft text", ["sentence 1: writes a digit"])]
        msgs = build_messages(DEMO, fb)
        self.assertEqual(msgs[-2], {"role": "assistant", "content": "bad draft text"})
        self.assertIn("sentence 1: writes a digit", msgs[-1]["content"])
        self.assertNotEqual(msgs, build_messages(DEMO))

    def test_prompt_shows_facts_not_a_finished_paragraph(self):
        user = build_messages(PUBLIC)[-1]["content"]
        self.assertIn("[[storage_low]]", user)
        self.assertIn("MUST MENTION", user)


class FakeSecondTry:
    """Always answers the same, wrong, text; shows a loop that never fixes itself is rejected after max drafts."""

    def chat(self, messages, temperature, seed, context=None, schema=None):
        return {"text": "Stable for 24 months.", "seconds": 0, "output_tokens": 3}


class RunLoop(unittest.TestCase):
    def test_mock_run_accepts_all_after_feedback(self):
        client = loop.StabilityMockClient()
        with tempfile.TemporaryDirectory() as d:
            s = run_p83(client, d, log=lambda *_: None)
            self.assertEqual((s["tasks"], s["accepted"], s["wrong_accepted"], s["rejected"]), (10, 10, [], []))
            self.assertTrue(all(client.saw_feedback.values()) and len(client.saw_feedback) == 10)
            self.assertEqual((s["seed"], s["temperature"]), (42, 0.0))
            tj = json.loads((Path(d) / "tasks.json").read_text(encoding="utf-8"))
            self.assertEqual((tj["seed"], tj["temperature"]), (42, 0.0))
            self.assertEqual(len(list((Path(d) / "sections").glob("*.md"))), 10)

    def test_never_fixing_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            s = run_p83(FakeSecondTry(), d, only=["p83_public"], log=lambda *_: None)
            self.assertEqual((s["accepted"], s["rejected"]), (0, ["p83_public"]))
            res = json.loads((Path(d) / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(len(res["drafts"]), loop.MAX_DRAFTS)


class Reread(unittest.TestCase):
    def finished(self, task, text):
        return loop.draft_problems(text, task)[1]

    def test_good_texts_pass_the_recount(self):
        for t in TASKS.values():
            self.assertEqual(reread.reread(self.finished(t, loop.mock_text(t)), t, ROWS), [], t["task_id"])

    def test_planted_wrong_number_public(self):
        text = self.finished(PUBLIC, GOOD_PUBLIC).replace("36 months when", "35 months when")
        self.assertTrue(reread.reread(text, PUBLIC, ROWS))

    def test_planted_wrong_number_demo(self):
        text = self.finished(DEMO, GOOD_DEMO).replace("99.28", "99.29")
        self.assertTrue(reread.reread(text, DEMO, ROWS))

    def test_planted_missing_label(self):
        text = self.finished(DEMO, GOOD_DEMO).replace("In illustrative demonstration data, ", "")
        self.assertTrue(reread.reread(text, DEMO, ROWS))

    def test_recount_catches_a_validator_blind_spot(self):
        """If the facts the validator trusts were wrong, the CSV recount still disagrees."""
        rows = [dict(r) for r in ROWS]
        for r in rows:
            if r["condition"] == "25C/60%RH" and r["attribute"] == "Assay" and r["month"] == "3":
                r["value"] = "99.00"
        text = self.finished(DEMO, GOOD_DEMO)
        self.assertTrue(reread.reread(text, DEMO, rows))


if __name__ == "__main__":
    unittest.main()
