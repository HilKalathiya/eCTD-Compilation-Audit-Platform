"""Tests the P.8.3 writer: placeholder checks, retry feedback, the independent CSV re-read; every check has a planted error that makes it fail."""
import json
import tempfile
import unittest
from pathlib import Path

from ectd_engine.stability import blind, facts as F, heldout, loop, plant, reread
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


QUIET = lambda *_: None  # noqa: E731


def heldout_csv(folder):
    """Write the held-out rows into folder and return the path."""
    path = Path(folder) / "heldout.csv"
    heldout.write_csv(path, heldout.generate())
    return path


class HeldoutData(unittest.TestCase):
    def test_rule_is_obeyed_and_repeatable(self):
        rows = heldout.generate()
        self.assertEqual(rows, heldout.generate())
        self.assertEqual(heldout.rule_check(rows), [])
        demo = [r for r in rows if r["source"] == heldout.SOURCE]
        self.assertEqual(len({(r["condition"], r["attribute"]) for r in demo}), 20)
        self.assertEqual(len(rows) - len(demo), 6)

    def test_planted_rule_breaks_are_caught(self):
        rows = [dict(r) for r in heldout.generate()]
        bad = [dict(r, limit="NMT 100000") if r["source"] == heldout.SOURCE else dict(r) for r in rows]  # nothing is outside any more
        self.assertTrue(any("outside the limit" in p for p in heldout.rule_check(bad)))
        dup = [dict(r) for r in rows] + [dict(rows[-1], condition="Refrigerated 5C 2")]
        self.assertTrue(any("is inside name" in p for p in heldout.rule_check(dup)))
        tuned = [dict(r, condition="25C/60%RH", attribute="Assay") for r in rows if r["source"] == heldout.SOURCE][:1]
        self.assertTrue(any("tuning data" in p for p in heldout.rule_check(rows + tuned)))

    def test_strict_default_check_still_rejects_what_heldout_allows(self):
        rows = F.load_rows(heldout_csv(tempfile.mkdtemp()))
        self.assertEqual(F.check_rows(rows, heldout=True), [])
        strict = F.check_rows(rows)
        self.assertTrue(any(p.startswith("bad_source") for p in strict))
        real = [dict(r) for r in F.load_rows() if r["attribute"] == "Assay" and r["month"] == "3"]
        real[0]["value"] = "150.0"
        real[0]["_line"] = 4
        self.assertIn("demo_outside_limit:line 4", F.check_rows(real))

    def test_held_out_source_is_not_a_demo_without_the_flag(self):
        self.assertIsNone(F.source_kind(heldout.SOURCE))
        self.assertEqual(F.source_kind(heldout.SOURCE, heldout=True), "demo")
        self.assertIsNone(F.source_kind("DEMO: synthetic held-out set T-066", heldout=True))


class HeldoutRun(unittest.TestCase):
    def test_mock_run_has_20_tasks_8_with_outside_results(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = heldout_csv(d)
            s = run_p83(loop.StabilityMockClient(), Path(d) / "run1", csv_path=csv_path, heldout=True, log=QUIET)
            self.assertEqual((s["tasks"], s["accepted"], s["wrong_accepted"], s["rejected"], s["retries_used"]), (20, 20, [], [], 20))
            tj = json.loads((Path(d) / "run1" / "tasks.json").read_text(encoding="utf-8"))["tasks"]
            self.assertEqual(sum("n_outside" in t["slots"] for t in tj), 8)
            self.assertNotIn("p83_public", [t["task_id"] for t in tj])

    def test_held_out_file_is_refused_without_the_flag(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                run_p83(loop.StabilityMockClient(), Path(d) / "run1", csv_path=heldout_csv(d), log=QUIET)

    def test_an_old_run_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            run_p83(loop.StabilityMockClient(), Path(d) / "run1", only=["p83_public"], log=QUIET)
            with self.assertRaises(FileExistsError):
                run_p83(loop.StabilityMockClient(), Path(d) / "run1", only=["p83_public"], log=QUIET)

    def test_wrong_number_in_an_accepted_text_is_flagged_by_the_recount(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = heldout_csv(d)
            tasks = {t["task_id"]: t for t in loop.make_tasks(F.p83_facts(F.load_rows(csv_path), True))}
            t = next(x for x in tasks.values() if "n_outside" in x["slots"])
            text = loop.draft_problems(loop.mock_text(t), t)[1]
            self.assertEqual(reread.reread(text, t, reread.read_rows(csv_path)), [])
            self.assertTrue(reread.reread(text.replace(" of its ", " of its 9"), t, reread.read_rows(csv_path)))


class FixesNothing:
    """A real-model stand-in that repeats the same bad text, so the retry test can report NOT FIXED."""

    def chat(self, messages, temperature, seed, context=None, schema=None):
        return {"text": "Stable for 24 months.", "seconds": 0, "output_tokens": 3}


class FixesFromFeedback:
    """A real-model stand-in that writes the right paragraph when asked again."""

    def chat(self, messages, temperature, seed, context=None, schema=None):
        return {"text": loop.mock_text(context["task"]), "seconds": 0, "output_tokens": 9}


class RetryTest(unittest.TestCase):
    def test_every_planted_draft_fails_the_checks_by_itself(self):
        with tempfile.TemporaryDirectory() as d:
            tasks = {t["task_id"]: t for t in loop.make_tasks(F.p83_facts(F.load_rows(heldout_csv(d)), True))}
            for tid, name in plant.choose(list(tasks.values())):
                self.assertTrue(problems(plant.PLANTS[name](tasks[tid]), tasks[tid]), name)

    def test_model_that_fixes_it_is_reported_fixed(self):
        with tempfile.TemporaryDirectory() as d:
            rep = plant.run_retry(FixesFromFeedback(), Path(d) / "retry", heldout_csv(d), log=QUIET)
            self.assertEqual(len(rep), 3)
            self.assertTrue(all(e["planted_was_rejected"] and e["fixed_by_model"] and e["drafts_used"] == 2 for e in rep))
            drafts = [json.loads(x) for x in (Path(d) / "retry" / "drafts.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sum(1 for x in drafts if x.get("planted")), 3)

    def test_model_that_does_not_fix_it_is_reported_not_fixed(self):
        with tempfile.TemporaryDirectory() as d:
            rep = plant.run_retry(FixesNothing(), Path(d) / "retry", heldout_csv(d), log=QUIET)
            self.assertTrue(all(e["planted_was_rejected"] and not e["fixed_by_model"] and not e["accepted"] for e in rep))


class BlindSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        d = Path(cls.tmp)
        cls.csv = heldout_csv(d)
        run_p83(loop.StabilityMockClient(), d / "held", csv_path=cls.csv, heldout=True, log=QUIET)
        run_p83(loop.StabilityMockClient(), d / "tune", log=QUIET)
        cls.held = blind.load_pool(d / "held", cls.csv, "held-out", True)
        cls.tune = blind.load_pool(d / "tune", F.DEFAULT_CSV, "tuning (T-064)", False)

    def test_22_right_and_3_planted_wrong_all_caught_by_the_recount(self):
        sheet, key = blind.build(self.held, self.tune)
        self.assertEqual((len(sheet), len(key)), (25, 25))
        self.assertEqual(sum(k["truth"] == "wrong" for k in key), 3)
        self.assertEqual(sum(k["set"] == "held-out" for k in key if k["truth"] == "right"), 17)  # 20 held-out minus the 3 made wrong
        self.assertEqual(sum(k["set"] == "held-out" for k in key if k["truth"] == "wrong"), 3)
        for k in key:
            if k["truth"] == "wrong":
                self.assertTrue(k["reread_flags"] and k["planted_change"])
                self.assertNotEqual(k["original_paragraph"], next(s["paragraph"] for s in sheet if s["row_id"] == k["row_id"]))

    def test_sheet_gives_no_hint_and_is_shuffled(self):
        sheet, key = blind.build(self.held, self.tune)
        self.assertEqual(list(sheet[0]), ["row_id", "paragraph", "csv_data", "hil_verdict", "hil_note"])
        self.assertTrue(all(s["hil_verdict"] == "" for s in sheet))
        self.assertNotEqual([k["truth"] for k in key], sorted(k["truth"] for k in key))
        self.assertNotEqual([k["task_id"] for k in key], sorted(k["task_id"] for k in key))

    def test_files_open_in_excel_with_degree_signs(self):
        sheet, key = blind.build(self.held, self.tune)
        p = Path(self.tmp) / "blind.csv"
        blind.write(p, sheet)
        self.assertTrue(p.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_small_pool_is_reported_not_padded(self):
        with self.assertRaises(ValueError):
            blind.build(self.held[:5], [])

    def test_each_mutation_is_caught_by_the_recount(self):
        out = next(p for p in self.held if "n_outside" in p["task"]["slots"])
        none = next(p for p in self.held if "n_outside" not in p["task"]["slots"])
        for p, fn in [(out, blind.wrong_outside), (out, blind.none_outside), (none, blind.none_outside), (none, blind.wrong_max)]:
            text, _ = fn(p["text"])
            self.assertTrue(reread.reread(text, p["task"], p["rows"]), fn.__name__)
            self.assertEqual(reread.reread(p["text"], p["task"], p["rows"]), [])


if __name__ == "__main__":
    unittest.main()
