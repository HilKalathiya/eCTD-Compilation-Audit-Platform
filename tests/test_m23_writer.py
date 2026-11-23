"""Tests for the 2.3 writer: a clean mock control must pass, and every planted bad draft (one defect each) must be rejected by the gate meant to catch it."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from ectd_engine.review import shapes as S
from ectd_engine.summary import m23_loop as L
from ectd_engine.summary import m23_tasks as T

INTRO = "In illustrative demonstration data, the drug product specification lists these tests and acceptance criteria."
PUBLIC = ("The proposed shelf life is [[shelf]] when stored at [[st_low]] to [[st_high]]. Excursions are permitted from [[ex_low]] to "
          "[[ex_high]]. Stability was demonstrated for [[long]] at long-term conditions and [[accel]] at accelerated conditions.")


def perfect(unit):
    """The correct draft for a unit, written from the unit's own words (what a good model would write)."""
    if unit["kind"] == "spec":
        return "\n".join([INTRO] + [f"{t}: {k} [[{s}]]" for (t, k), s in zip(unit["rows"], unit["required"])])
    if unit["kind"] == "public":
        return PUBLIC
    n = unit["names"]
    return f"In illustrative demonstration data, {n['attr'][0]} under {n['cond'][0]} conditions ranged from [[low]] to [[high]]."


def stub_messages(view, feedback):
    """A stand-in prompt for these tests: the digit-free view and the feedback, as one message."""
    return [{"role": "user", "content": json.dumps({"view": view, "feedback": feedback})}]


class Scripted:
    """A fake model. script(unit_id, draft_number, perfect_text) -> text; default = always the perfect text."""

    def __init__(self, task, script=None):
        self.units = {u["unit_id"]: u for u in T.units_of(task)}
        self.script, self.calls, self.seen = script, {}, []

    def chat(self, messages, temperature, seed, context=None, schema=None):
        uid = context["unit_id"]
        n = self.calls.get(uid, 0)
        self.calls[uid] = n + 1
        self.seen.append((uid, n, messages, seed, temperature))
        text = perfect(self.units[uid])
        if self.script:
            text = self.script(uid, n, text)
        return {"text": text, "seconds": 0.0, "output_tokens": 0}


def unit_of(task, kind, which=0):
    return [u for u in T.units_of(task) if u["kind"] == kind][which]


class Control(unittest.TestCase):
    """The clean mock control: perfect drafts pass every gate, including the cross-check of the saved HTML and Word file."""

    def run_world(self, task, client=None, **kw):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "w"
        client = client or Scripted(task)
        return out, L.run_world(client, task, out, build_messages=stub_messages, **kw)

    def test_synthetic_control_passes_all_gates_with_no_retry(self):
        task = T.synthetic_task("dev", 1)
        out, res = self.run_world(task)
        self.assertTrue(res["accepted"], res)
        self.assertEqual(set(res["drafts"].values()), {1})
        self.assertTrue((out / "render_1" / "M23.html").exists() and (out / "render_1" / "M23.docx").exists())
        csv = (out / "render_1" / "crosscheck.csv").read_text(encoding="utf-8-sig")
        self.assertNotIn("FAIL", csv)
        self.assertNotIn("unplaced", csv)
        self.assertIn("synthetic test case", (out / "render_1" / "M23.html").read_text(encoding="utf-8"))

    def test_real_task_control_passes_with_zero_failed_and_zero_unplaced(self):
        task = T.real_task()
        out, res = self.run_world(task)
        self.assertTrue(res["accepted"], res)
        for fmt in ("html", "docx"):
            c = res["counts"][fmt]
            self.assertEqual((c["failed"], c["uncovered"]), (0, 0))
            self.assertEqual(c["checked"], c["matched"])
        self.assertNotIn("synthetic", (out / "render_1" / "M23.html").read_text(encoding="utf-8"))

    def test_every_dev_and_heldout_task_control_passes(self):
        for which, tasks in (("dev", range(1, T.DEV_COUNT + 1)), ("heldout", range(1, T.HELD_COUNT + 1))):
            for i in tasks:
                task = T.synthetic_task(which, i)
                _, res = self.run_world(task)
                self.assertTrue(res["accepted"], (task["task_id"], res))

    def test_a_run_folder_is_never_overwritten(self):
        task = T.synthetic_task("dev", 1)
        out, _ = self.run_world(task)
        with self.assertRaises(FileExistsError):
            L.run_world(Scripted(task), task, out, build_messages=stub_messages)


class Planted(unittest.TestCase):
    """Each planted draft = the correct draft with exactly ONE defect. The gate meant to catch it must fire, and the world must be rejected."""

    @classmethod
    def setUpClass(cls):
        cls.task = T.synthetic_task("dev", 4)        # shelf life and long-term months are the same number in this task
        v = {k: s["value"] for k, s in cls.task["public"].items()}
        assert v["shelf"] == v["long"]

    def defect_world(self, kind, mutate, which=0):
        """Run a whole world where the model always writes the one defective draft for that unit; return (result, attempts, folder)."""
        unit = unit_of(self.task, kind, which)

        def script(uid, n, text):
            return mutate(text) if uid == unit["unit_id"] else text
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "w"
        res = L.run_world(Scripted(self.task, script), self.task, out, build_messages=stub_messages)
        attempts = [json.loads(x) for x in (out / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
        return unit, res, attempts, out

    def assert_rejected_by(self, kind, mutate, gate, which=0):
        unit, res, attempts, out = self.defect_world(kind, mutate, which)
        control_problems, _ = L.gate_unit(unit, perfect(unit))
        self.assertEqual(control_problems, [], "the control must pass")
        problems, _ = L.gate_unit(unit, mutate(perfect(unit)))
        self.assertTrue(any(p.startswith(f"({gate})") for p in problems), problems)
        self.assertFalse(res["accepted"])
        self.assertEqual(res["drafts"][unit["unit_id"]], L.MAX_DRAFTS)
        self.assertTrue(all(not a["passed"] for a in attempts if a.get("unit_id") == unit["unit_id"]))
        self.assertFalse((out / "render_1").exists(), "a rejected unit must never reach rendering")
        return problems

    def test_a_digit(self):
        self.assert_rejected_by("result", lambda t: t.replace(" to [[high]].", " to [[high]] in 3 batches."), "a")

    def test_a_number_word(self):
        p = self.assert_rejected_by("result", lambda t: t.replace(" to [[high]].", " to [[high]] across three batches."), "a")
        self.assertTrue(any("number word" in x for x in p))

    def test_a_degree_sign(self):
        self.assert_rejected_by("public", lambda t: t.replace("[[st_low]] to", "[[st_low]]° to"), "a")

    def test_unknown_slot(self):
        p = self.assert_rejected_by("result", lambda t: t.replace("[[high]]", "[[maximum]]"), "b")
        self.assertTrue(any("not in the FACTS list" in x for x in p))

    def test_missing_required_slot(self):
        p = self.assert_rejected_by("result", lambda t: t.replace(" to [[high]]", ""), "b")
        self.assertTrue(any("missing placeholder [[high]]" in x for x in p))

    def test_a_slot_used_twice(self):
        self.assert_rejected_by("result", lambda t: t.replace("[[high]]", "[[low]]"), "b")

    def test_shelf_life_slot_used_as_storage(self):
        # the shelf-life slot and the storage-low slot swap places: every slot is used once, but not in its own place
        swap = lambda t: t.replace("[[shelf]]", "[[@]]").replace("[[st_low]]", "[[shelf]]").replace("[[@]]", "[[st_low]]")  # noqa: E731
        unit, res, _, _ = self.defect_world("public", swap)
        problems, _ = L.gate_unit(unit, swap(perfect(unit)))
        self.assertTrue(problems)
        self.assertFalse(res["accepted"])

    def test_coincident_values_swapped_between_places_is_caught_by_the_slot_binding(self):
        # shelf life and long-term months have the SAME number here, so the finished text looks right; only the slot check can see the swap
        swap = lambda t: t.replace("[[shelf]]", "[[@]]").replace("[[long]]", "[[shelf]]").replace("[[@]]", "[[long]]")  # noqa: E731
        unit = unit_of(self.task, "public")
        rendered_perfect = [re.sub(r"\[\[(\w+)\]\]", lambda m: unit["slots"][m.group(1)]["text"], s) for s in L.split_draft(unit, perfect(unit))]
        rendered_swapped = [re.sub(r"\[\[(\w+)\]\]", lambda m: unit["slots"][m.group(1)]["text"], s) for s in L.split_draft(unit, swap(perfect(unit)))]
        self.assertEqual(rendered_perfect, rendered_swapped, "the swap must be invisible to a value check")
        p = self.assert_rejected_by("public", swap, "b")
        self.assertTrue(any("each value belongs to its own place" in x for x in p))

    def test_demo_label_dropped(self):
        self.assert_rejected_by("result", lambda t: t.replace("In illustrative demonstration data, ", ""), "c")

    def test_demo_label_added_to_a_public_sentence(self):
        self.assert_rejected_by("public", lambda t: "In illustrative demonstration data, " + t[0].lower() + t[1:], "c")

    def test_overclaim_sentence_fully_demonstrates(self):
        p = self.assert_rejected_by("result", lambda t: t + " This fully demonstrates stability.", "c")
        self.assertTrue(any(x.startswith("(e)") for x in p), "the vocabulary gate must fire on its own as well")

    def test_overclaim_no_change_observed_while_results_are_outside_the_limit(self):
        # a task fact says 2 results are outside the limit; the draft still claims no change. No form allows that sentence.
        p = self.assert_rejected_by("result", lambda t: t + " No change was observed.", "c")
        self.assertTrue(any(x.startswith("(e)") for x in p))

    def test_extra_citation_not_in_the_registry(self):
        self.assert_rejected_by("result", lambda t: t.replace(" to [[high]].", " to [[high]] (ICH Q99)."), "a")

    def test_a_citation_that_IS_in_the_registry_is_still_not_allowed_in_a_draft(self):
        self.assert_rejected_by("result", lambda t: t.replace(" to [[high]].", " to [[high]] (ICH Q3B(R2))."), "a")

    def test_a_sentence_of_unknown_shape(self):
        p = self.assert_rejected_by("public", lambda t: "The product is widely accepted. " + t, "c")
        self.assertTrue(any("unrecognised" in x or "needs exactly" in x for x in p))

    def test_spec_row_with_the_wrong_test_name(self):
        unit = unit_of(self.task, "spec")
        t0, t1 = unit["rows"][0][0], unit["rows"][1][0]
        self.assert_rejected_by("spec", lambda t: t.replace(f"{t0}: ", "@@").replace(f"{t1}: ", f"{t0}: ").replace("@@", f"{t1}: "), "c")

    def test_a_period_after_a_spec_row_is_refused(self):
        self.assert_rejected_by("spec", lambda t: t.replace("]]", "]].", 1), "c")


class VocabularyGate(unittest.TestCase):
    """Gate (e) on its own: words outside the closed vocabulary are found; the allowlist is not a blocklist."""

    def test_overclaim_words_are_unknown_not_blocked(self):
        vocab = S.m23_vocabulary(["Assay", "long-term"])
        self.assertEqual(S.m23_unknown_words("Assay under long-term conditions ranged from to.", vocab), [])
        self.assertEqual(S.m23_unknown_words("This fully demonstrates robust stability", vocab), ["This", "demonstrates", "fully", "robust", "stability"])
        # a harmless word that nobody listed is also refused: default = reject
        self.assertEqual(S.m23_unknown_words("Assay is great", vocab), ["great"])        # "is" is a word of the fixed forms
        self.assertEqual(S.m23_unknown_words("Assay is excellent", vocab), ["excellent"])


class CrosscheckGate(unittest.TestCase):
    """Gate (d) on its own: a document that passes a, b, c and e is still rejected when the cross-check finds a number that differs from the graph."""

    def test_graph_value_changed_after_writing_rejects_the_world(self):
        task = T.synthetic_task("dev", 1)
        rows = copy.deepcopy(task["graph_rows"])
        shelf_id = task["public"]["shelf"]["fact_id"]
        rows[shelf_id]["value_text"] = str(int(rows[shelf_id]["value_text"]) + 1)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "w"
        res = L.run_world(Scripted(task), task, out, rows=rows, build_messages=stub_messages)
        self.assertFalse(res["accepted"])
        self.assertTrue(res["reason"].startswith("(d)"), res)
        self.assertIn("2.3 value differs from the graph value", (out / "render_1" / "crosscheck.csv").read_text(encoding="utf-8-sig"))
        attempts = [json.loads(x) for x in (out / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(a.get("gate") == "d" and not a["passed"] for a in attempts))

    def test_an_extra_number_in_the_saved_file_becomes_its_own_unplaced_row(self):
        from ectd_engine.summary import crosscheck as X
        task = T.synthetic_task("dev", 1)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "w"
        res = L.run_world(Scripted(task), task, out, build_messages=stub_messages)
        self.assertTrue(res["accepted"])
        html_path = out / "render_1" / "M23.html"
        html_path.write_text(html_path.read_text(encoding="utf-8").replace("conditions ranged", "conditions in 7 batches ranged", 1), encoding="utf-8")
        ref = (out / "ref" / "p5_placements.jsonl", out / "ref" / "p8")
        cc = X.run(out / "render_1", task["graph_rows"], *ref)
        self.assertFalse(cc["passed"])
        self.assertEqual([r["fact_id"] for r in cc["rows"] if r["fact_id"].startswith("unplaced:")], ["unplaced:7"])


class Retry(unittest.TestCase):
    """A rejected draft is sent back with its problems; nothing numeric travels back to the model."""

    def test_retry_with_feedback_then_accept_and_no_digit_in_the_feedback(self):
        task = T.synthetic_task("dev", 2)
        unit = unit_of(task, "result")

        def script(uid, n, text):
            return text.replace(" to [[high]].", " to [[high]] in 12 batches.") if uid == unit["unit_id"] and n == 0 else text
        client = Scripted(task, script)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        res = L.run_world(client, task, Path(tmp.name) / "w", build_messages=stub_messages)
        self.assertTrue(res["accepted"], res)
        self.assertEqual(res["drafts"][unit["unit_id"]], 2)
        second = [m for uid, n, m, seed, temp in client.seen if uid == unit["unit_id"] and n == 1][0]
        text = second[0]["content"]
        self.assertIn("(a)", text)
        self.assertNotRegex(json.dumps(json.loads(text)["feedback"]), r"\d")
        # the seed is 42 for the first draft and moves by one for each retry; temperature is 0
        self.assertEqual([(n, seed, temp) for uid, n, m, seed, temp in client.seen if uid == unit["unit_id"]], [(0, 42, 0.0), (1, 43, 0.0)])


if __name__ == "__main__":
    unittest.main()
