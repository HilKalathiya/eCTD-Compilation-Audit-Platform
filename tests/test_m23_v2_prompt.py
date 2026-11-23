"""Tests for the T-072 prompt (no digit, no value, no answer text, example from another attribute) and for the copy-rate metric."""
import json
import tempfile
import unittest
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.review import shapes as S
from ectd_engine.summary import m23_loop2 as L
from ectd_engine.summary import m23_prompt as MP
from ectd_engine.summary import m23_run2 as R
from ectd_engine.summary import m23_tasks2 as T
from tests.test_m23_v2_writer import compose


def all_units():
    """[(task id, unit, rows)] for the real task and every dev and held-out task."""
    out = []
    real = T.real_task()
    out += [(real["task_id"], u, G.collect()) for u in T.units_of(real, G.collect())]
    for which, items in T.all_tasks().items():
        for t, rows in items:
            if rows is not None:
                out += [(t["task_id"], u, rows) for u in T.units_of(t, rows)]
    return out


class PromptHasNoNumbersAndNoAnswer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units = all_units()

    def text(self, unit, feedback=()):
        return "\n".join(m["content"] for m in MP.build_messages(T.view_of(unit), feedback))

    def test_no_digit_in_any_message_of_any_unit(self):
        for tid, u, _ in self.units:
            self.assertNotRegex(self.text(u), r"\d", (tid, u["unit_id"]))

    def test_no_value_and_no_fact_id_in_any_message(self):
        for tid, u, _ in self.units:
            text = self.text(u)
            for s in u["slots"].values():
                self.assertNotIn(s["text"], text)
                self.assertNotIn(s["fact_id"], text)

    def test_the_old_answer_instruction_is_gone(self):
        for tid, u, _ in self.units[:5]:
            self.assertNotIn("WRITE EXACTLY", self.text(u))
        self.assertNotIn("WRITE EXACTLY", MP.SYSTEM)

    def test_no_correct_answer_in_any_wording_appears_in_the_unit_messages(self):
        """Fill every allowed wording with the unit's own words and slot names: not one of those drafts, and not one of their sentences, is in the prompt."""
        longest = max(len(v) for v in S.M23B_SHAPES.values())
        for tid, u, _ in self.units:
            text = self.text(u)
            for k in range(longest):
                draft = compose(u, {kind: k for kind in S.M23B_SHAPES})
                self.assertNotIn(draft, text, (tid, u["unit_id"], k))
                for sentence in L.split_draft(u, draft):
                    if "[[" in sentence:           # a sentence with no slot (the specification intro) is checked by the copy metric instead
                        self.assertNotIn(sentence, text, (tid, u["unit_id"], k, sentence))

    def test_the_example_is_about_another_attribute_with_other_placeholder_names(self):
        for tid, u, _ in self.units:
            q, a = MP.example_for(T.view_of(u))
            example = q + "\n" + a
            for name in u["slots"]:
                self.assertNotIn("[[" + name + "]]", example, (tid, u["unit_id"], name))
            for word in (u["words"][:1] if u["kind"] == "result" else u["words"]):      # the attribute / test names (a condition word may repeat: only three exist)
                self.assertNotIn(word, example, (tid, u["unit_id"], word))
            self.assertNotEqual(q.split("\n")[0], "", "the example has a UNIT line")

    def test_the_example_matches_the_unit_type_and_the_outside_state(self):
        by_kind = {}
        for tid, u, _ in self.units:
            q, _ = MP.example_for(T.view_of(u))
            by_kind.setdefault(u["kind"], set()).add(q.split("\n")[0])
            if u["kind"] == "result":
                self.assertIn(f"OUTSIDE LIMIT: {'none' if u['outside'] == 0 else 'some'}", q)
                self.assertEqual("[[tp]]" in u["context"]["attribute"], "[[minutes]]" in q)
        self.assertEqual(by_kind, {"spec": {"UNIT: specification"}, "public": {"UNIT: public"}, "result": {"UNIT: results"}})

    def test_every_example_answer_is_itself_accepted_wording(self):
        """The examples teach only wordings the closed list accepts (checked with each example's own words)."""
        fill = {"smallest": "5.0%", "largest": "7.0%", "shortest": "5.0%", "longest": "7.0%", "minutes": "15 min", "period": "24 months",
                "cold_end": "5°C", "warm_end": "25°C", "dip": "0°C", "peak": "40°C", "slow_run": "12 months", "fast_run": "6 months",
                "limit_colour": "5.0%", "limit_hardness": "80%"}
        names = {"test": ["Colour", "Hardness"], "kind": ["NMT", "NLT"], "attr": ["Hardness", "Disintegration (15 min)"], "cond": ["accelerated", "intermediate"]}
        examples = [MP.example_for({"kind": "spec", "context": {}})[1], MP.example_for({"kind": "public", "context": {}})[1]]
        examples += [MP._result_example(o)[1] for o in ("none", "some")] + [MP._timed_result_example(o)[1] for o in ("none", "some")]
        import re
        for a in examples:
            sentences = [x for x in re.split(r"(?<=\.)\s+|\n", re.sub(r"\[\[(\w+)\]\]", lambda m: fill[m.group(1)], a).strip()) if x]
            for s in sentences:
                self.assertIsNotNone(S.m23b_classify(s, names), s)
        self.assertEqual(len(examples), 6)

    def test_feedback_turns_carry_no_digit_and_a_digit_is_refused(self):
        tid, u, _ = self.units[0]
        msgs = MP.build_messages(T.view_of(u), [(L._clean("Colour: NMT 5 and 36 months"), [L._clean("(a) writes a digit in 36 months")])])
        self.assertEqual(len(msgs), 6)
        self.assertNotRegex(" ".join(m["content"] for m in msgs), r"\d")
        with self.assertRaises(ValueError):
            MP.build_messages(T.view_of(u), [("36 months", ["x"])])

    def test_the_unit_message_tells_the_outside_state_in_words_only(self):
        for tid, u, _ in self.units:
            if u["kind"] == "result":
                self.assertIn("OUTSIDE LIMIT: " + ("none" if u["outside"] == 0 else "some"), self.text(u))


class CopyMetric(unittest.TestCase):
    def attempts(self, text, content):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "attempts.jsonl"
        p.write_text(json.dumps({"unit_id": "u", "passed": True, "text": text, "messages": [{"role": "user", "content": content}]}) + "\n", encoding="utf-8")
        return p

    def test_a_draft_copied_from_the_prompt_is_counted_at_every_level(self):
        text = "In illustrative demonstration data, Hardness was between [[a]] and [[b]]."
        got = R.copy_stats(self.attempts(text, "EXAMPLE\n" + text + "\nASK"))
        self.assertEqual((got["units"], got["whole"], got["sentences_copied"], got["skeleton_sentences_copied"]), (1, 1, 1, 1))

    def test_the_same_wording_with_other_slot_names_counts_only_as_a_skeleton_copy(self):
        got = R.copy_stats(self.attempts("Hardness was between [[low]] and [[high]].", "EXAMPLE Hardness was between [[smallest]] and [[largest]]. ASK"))
        self.assertEqual((got["whole"], got["sentences_copied"], got["skeleton_sentences_copied"]), (0, 0, 1))

    def test_a_new_wording_is_not_a_copy(self):
        got = R.copy_stats(self.attempts("Assay ranged from [[low]] to [[high]].", "EXAMPLE Hardness was between [[smallest]] and [[largest]]. ASK"))
        self.assertEqual((got["whole"], got["sentences_copied"], got["skeleton_sentences_copied"]), (0, 0, 0))

    def test_only_accepted_drafts_are_counted(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "a.jsonl"
        p.write_text(json.dumps({"unit_id": "u", "passed": False, "text": "x", "messages": [{"content": "x"}]}) + "\n"
                     + json.dumps({"gate": "d", "passed": True}) + "\n", encoding="utf-8")
        self.assertEqual(R.copy_stats(p)["units"], 0)


if __name__ == "__main__":
    unittest.main()
