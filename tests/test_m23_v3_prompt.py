"""Tests for the T-073 prompt (no answer sentence anywhere, no digit, the DEMONSTRATED line), the closed shape set (provenance) and the two copy rates."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from ectd_engine.review import shapes as S
from ectd_engine.summary import m23_prompt3 as PR
from ectd_engine.summary import m23_run3 as RUN
from ectd_engine.summary import m23_tasks3 as T

FIELD = re.compile(r"\{(s|test|attr|cond|kind)\}")


def wildcard(template):
    """A regex that matches the wording with ANY slot, test, attribute or condition in its fields (so a renamed copy is found too)."""
    out, pos = [], 0
    for m in FIELD.finditer(template):
        out.append(re.escape(template[pos:m.start()]))
        out.append(r"(?:\[\[[a-z_]+\]\]|\d+(?:\.\d+)?\S*|[A-Za-z][A-Za-z() \[\]-]*?)")
        pos = m.end()
    out.append(re.escape(template[pos:]))
    return re.compile("".join(out))


class Prompt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units = []
        for t, rows in T.all_tasks3()["dev"][:4]:
            cls.units += T.units_of3(t, rows)

    def test_there_is_no_example_turn_only_a_system_and_a_user_message(self):
        for u in self.units:
            msgs = PR.build_messages(T.view_of(u))
            self.assertEqual([m["role"] for m in msgs], ["system", "user"])

    def test_no_digit_reaches_the_model_not_even_in_feedback(self):
        for u in self.units:
            for m in PR.build_messages(T.view_of(u), [("a draft [[low]]", ["(c) problem"])]):
                self.assertNotRegex(m["content"], r"\d")
        with self.assertRaises(ValueError):
            PR.build_messages(T.view_of(self.units[0]), [("a draft with 5", ["x"])])

    def test_no_accepted_sentence_wording_is_in_any_prompt_even_with_other_names(self):
        for u in self.units:
            text = "\n".join(m["content"] for m in PR.build_messages(T.view_of(u)))
            for kind, shapes in S.M23C_SHAPES.items():
                for name, template, _, _ in shapes:
                    if kind != "spec_row":                      # "<test>: <kind> <slot>" is a line format, checked on its own below
                        self.assertIsNone(wildcard(template).search(text), (u["unit_id"], name))
            self.assertIsNone(re.search(r"^[^\n]*(?:NMT|NLT) \[\[[a-z_]+\]\]\s*$", text, re.M), u["unit_id"])
        self.assertNotIn("lists these tests", PR.SYSTEM)
        self.assertNotIn("lists the tests and their acceptance criteria", PR.SYSTEM + "".join(PR.build_messages(T.view_of(self.units[0]))[1]["content"]))

    def test_the_prompt_never_holds_a_sentence_of_the_old_examples(self):
        old = ["was between [[smallest]]", "Hardness", "Colour", "Disintegration", "[[period]]", "[[cold_end]]", "[[smallest]]"]
        for u in self.units:
            text = "\n".join(m["content"] for m in PR.build_messages(T.view_of(u)))
            for piece in old:
                self.assertNotIn(piece, text)

    def test_the_public_unit_says_whether_demonstrated_is_allowed(self):
        seen = set()
        for t, rows in T.all_tasks3()["dev"]:
            pub = next(u for u in T.units_of3(t, rows) if u["kind"] == "public")
            line = next(l for l in PR.unit_message(T.view_of(pub)).splitlines() if l.startswith("DEMONSTRATED:"))
            self.assertEqual(line, "DEMONSTRATED: " + ("not allowed" if pub["study_blockers"] else "allowed"))
            seen.add(line)
        self.assertEqual(len(seen), 2)

    def test_the_menu_is_the_closed_list_with_blanks_and_holds_no_finished_sentence(self):
        for u in self.units:
            menu = PR.wording_menu(T.view_of(u))
            self.assertNotRegex(menu, r"\d")
            patterns = [l[4:] for l in menu.splitlines() if l.startswith("  - ")]
            self.assertTrue(patterns)
            self.assertNotIn("[[", "\n".join(patterns))               # a pattern holds <blanks>, never a placeholder
            for p in patterns:
                self.assertRegex(p, r"<[^>]+>", p)                    # every pattern still has a blank to fill, so it is not an answer as it stands
            if u["kind"] == "public":
                # filling the blanks of every menu pattern with the unit's own slots gives a sentence the gate accepts: the menu and the gate agree
                for p in patterns:
                    text = re.sub(r"<([a-z_]+)>", lambda m: u["slots"][m.group(1)]["text"], p)
                    kind = S.m23c_classify(text, {}, kinds=("shelf", "excursion", "study"))
                    self.assertIsNotNone(kind, p)
                    self.assertFalse(kind[2] == "clean" and u["study_blockers"], p)       # a "demonstrated" wording is not offered when it is not allowed

    def test_the_two_intro_patterns_are_exactly_the_two_intro_wordings_once_filled(self):
        filled = {p.replace("<word-a>", "these").replace("<word-b>", "the") for p in PR.INTRO_PATTERNS}
        self.assertEqual(filled, {t for _, t, _, _ in S.M23C_SHAPES["spec_intro"]})
        for p in PR.INTRO_PATTERNS:
            self.assertIsNone(S.m23c_classify(p, {}))                 # as they stand they are not accepted sentences

    def test_the_menu_offers_only_claim_wordings_that_fit_the_count(self):
        for u in self.units:
            if u["kind"] == "result":
                menu = PR.wording_menu(T.view_of(u))
                self.assertEqual("had results outside the limit" in menu, u["outside"] > 0)
                self.assertEqual("within the specification limits" in menu or "had no results outside" in menu, u["outside"] == 0)

    def test_the_system_message_defines_the_label_and_the_demonstrated_rule(self):
        self.assertIn('"In illustrative demonstration data,"', PR.SYSTEM)
        self.assertIn("DEMONSTRATED: not allowed", PR.SYSTEM)


class Shapes(unittest.TestCase):
    def test_the_two_wordings_that_came_from_a_model_draft_are_not_in_the_third_set(self):
        names = {n for shapes in S.M23C_SHAPES.values() for n, *_ in shapes}
        self.assertFalse({"exc_c", "exc_d"} & names)
        self.assertTrue({"exc_c", "exc_d"} <= {n for shapes in S.M23B_SHAPES.values() for n, *_ in shapes})     # the T-072 set is left as it was

    def test_neutral_study_wordings_exist_and_the_demonstrated_ones_are_tagged(self):
        by = {n: needs for n, _, _, needs in S.M23C_SHAPES["study"]}
        for n, t, _, needs in S.M23C_SHAPES["study"]:
            self.assertEqual("demonstrated" in t, needs == "clean", n)
        self.assertGreaterEqual(sum(1 for v in by.values() if v is None), 3)

    def test_every_study_wording_needs_both_the_long_term_and_accelerated_slot(self):
        for n, t, slots, _ in S.M23C_SHAPES["study"]:
            self.assertEqual(slots, ("long", "accel"), n)


class CopyRates(unittest.TestCase):
    def attempt(self, prompt_user, draft, passed=True):
        return {"task_id": "t", "unit_id": "u", "passed": passed, "text": draft,
                "messages": [{"role": "system", "content": "SYS"}, {"role": "user", "content": prompt_user}]}

    def stats(self, *attempts):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "attempts.jsonl"
            p.write_text("\n".join(json.dumps(a) for a in attempts) + "\n", encoding="utf-8")
            return RUN.copy_stats(p)

    def test_an_exact_copy_counts_in_both_rates(self):
        s = self.stats(self.attempt("see: In illustrative demonstration data, Assay under long-term conditions ranged from [[low]] to [[high]].",
                                    "In illustrative demonstration data, Assay under long-term conditions ranged from [[low]] to [[high]]."))
        self.assertEqual((s["sentences"], s["sentences_copied"], s["blanked_sentences_copied"]), (1, 1, 1))

    def test_a_copy_with_other_names_is_counted_only_after_blanking(self):
        s = self.stats(self.attempt("see: In illustrative demonstration data, Assay under long-term conditions ranged from [[low]] to [[high]].",
                                    "In illustrative demonstration data, Degradation product under accelerated conditions ranged from [[a]] to [[b]]."))
        self.assertEqual((s["sentences_copied"], s["blanked_sentences_copied"]), (0, 1))

    def test_a_new_sentence_is_in_neither_rate_and_rejected_drafts_are_not_counted(self):
        s = self.stats(self.attempt("nothing here", "In illustrative demonstration data, Assay was between [[low]] and [[high]]."),
                       self.attempt("x", "x", passed=False))
        self.assertEqual((s["units"], s["sentences"], s["sentences_copied"], s["blanked_sentences_copied"], s["whole"]), (1, 1, 0, 0, 0))

    def test_blank_replaces_placeholders_and_names_only(self):
        self.assertEqual(RUN.blank("Assay under long-term conditions: [[low]]"), "<name> under <name> conditions: [[]]")


if __name__ == "__main__":
    unittest.main()
