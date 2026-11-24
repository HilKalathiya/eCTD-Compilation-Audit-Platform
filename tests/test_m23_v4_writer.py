"""Tests for the T-074 2.3 writer (a template filler): clean controls, every gate planted both ways, the review route, no claim without a spec fact, the metrics and the prompt."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.review import shapes as S
from ectd_engine.summary import m23_compare4 as C4
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import m23_loop4 as L
from ectd_engine.summary import m23_prompt4 as PR
from ectd_engine.summary import m23_rules4 as R
from ectd_engine.summary import m23_run4 as RUN
from ectd_engine.summary import m23_tasks4 as T4
from ectd_engine.summary import plan as P

PH_FIELD = re.compile(r"\{(s|test|attr|cond|kind)\}")


def stub_messages(view, feedback):
    return [{"role": "user", "content": json.dumps({"view": view, "feedback": feedback})}]


class FakeGraph:
    namespace = "TEST"

    def __init__(self, rows):
        self._rows = rows

    def rows(self):
        return copy.deepcopy(self._rows)


def compose(unit, choice=None, force=None):
    """The correct draft for a unit. force = {kind: shape name} picks one pattern whatever the data say (to plant a wrong choice)."""
    choice, force, lines = choice or {}, force or {}, []
    for j, kind in enumerate(unit["expect"]):
        shapes = S.M23D_SHAPES[kind]
        if kind == "claim":
            shapes = [x for x in shapes if x[3] == ("zero" if unit["outside"] == 0 else "some")]
        if kind == "study" and unit["study_blockers"]:
            shapes = [x for x in shapes if x[3] is None]
        name, template, slots, _ = next(x for x in S.M23D_SHAPES[kind] if x[0] == force[kind]) if kind in force else shapes[choice.get(kind, 0) % len(shapes)]
        plain = iter([s for s in slots if s != "attr"])

        def sub(m, j=j, kind=kind):
            f = m.group(1)
            if f == "s":
                return "[[" + (unit["rows"][j - 1][2] if kind == "spec_row" else next(plain)) + "]]"
            if f == "attr":
                return unit["attr_template"]
            if f == "cond":
                return unit["names"]["cond"][0]
            if f == "test":
                return unit["rows"][j - 1][0]
            return unit["rows"][j - 1][1]
        lines.append(PH_FIELD.sub(sub, template))
    return "\n".join(lines) if unit["kind"] == "spec" else " ".join(lines)


class Scripted:
    def __init__(self, task, rows, script=None, choice=None, force=None):
        self.units = {u["unit_id"]: u for u in T4.units_of4(task, rows)}
        self.script, self.choice, self.force, self.calls = script, choice, force, {}

    def chat(self, messages, temperature, seed, context=None, schema=None):
        uid = context["unit_id"]
        n = self.calls.get(uid, 0)
        self.calls[uid] = n + 1
        text = compose(self.units[uid], self.choice, self.force)
        if self.script:
            text = self.script(uid, n, text)
        return {"text": text, "seconds": 0.0, "output_tokens": 0}


def synthetic(which, i):
    task, rows = T4.synthetic_task4(which, i)
    return task, rows, MG.MemoryGraph(rows)


def run(task, graph, client, **kw):
    tmp = tempfile.TemporaryDirectory()
    out = Path(tmp.name) / "w"
    res = L.run_world(client, task, out, graph, build_messages=stub_messages, **kw)
    return tmp, out, res


def by_profile(profile, which="dev"):
    i = next(i for i in range(1, 11) if T4.PROFILES[i - 1] == profile)
    return synthetic(which, i)


def snapshot(out):
    return json.loads((out / "graph_snapshot_check.json").read_text(encoding="utf-8"))


class Control(unittest.TestCase):
    def test_every_task_passes_all_gates_and_the_independent_comparer(self):
        for which, n in (("dev", T4.DEV_COUNT), ("heldout", T4.HELD_COUNT)):
            for i in range(1, n + 1):
                task, rows, graph = synthetic(which, i)
                tmp, out, res = run(task, graph, Scripted(task, rows))
                self.addCleanup(tmp.cleanup)
                self.assertTrue(res["accepted"], (task["task_id"], res))
                self.assertEqual(set(res["drafts"].values()), {1})
                cmp_ = C4.compare(out / res["render"] / "M23.html", task, snapshot(out))
                self.assertEqual(cmp_["problems"], [], task["task_id"])
                self.assertEqual(cmp_["review"], bool(R.review_reasons(rows, R.links_of(task))))
                self.assertEqual(res["review_route"], cmp_["review"])

    def test_the_real_task_renders_with_range_only_for_assay_and_degradation(self):
        rows, task = G.collect(), T4.real_task4()
        tmp, out, res = run(task, FakeGraph(rows), Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        self.assertTrue(res["accepted"], res)
        cmp_ = C4.compare(out / res["render"] / "M23.html", task, snapshot(out))
        self.assertEqual(cmp_["problems"], [])
        self.assertEqual({v for k, v in cmp_["pattern"].items() if "Dissolution" not in k}, {"range_only"})
        self.assertEqual({v for k, v in cmp_["pattern"].items() if "Dissolution" in k}, {"none"})
        self.assertFalse(res["review_route"])
        self.assertEqual(res["counts"]["html"]["failed"], 0)
        self.assertEqual(res["counts"]["docx"]["failed"], 0)

    def test_every_gate_letter_is_named(self):
        self.assertEqual(L.gate_tags(["(a) x", "(c) y", "(c) z", "(i) w", "no tag"]), {"a", "c", "i"})


def good_then(bad_text_fn):
    """A script: the first draft of the unit is bad_text_fn(good text); afterwards the good text."""
    def script(uid, n, text):
        return bad_text_fn(uid, text) if n == 0 else text
    return script


class GatesPlantedBothWays(unittest.TestCase):
    def go(self, task, rows, graph, script=None, **kw):
        tmp, out, res = run(task, graph, Scripted(task, rows, script=script, **kw))
        self.addCleanup(tmp.cleanup)
        attempts = [json.loads(x) for x in (out / "attempts.jsonl").read_text(encoding="utf-8").splitlines()] if (out / "attempts.jsonl").exists() else []
        return out, res, attempts

    def test_f_claim_polarity_both_ways(self):
        for profile, wrong_kind in (("clean", "claim_d"), ("outside_accel", "claim_a")):
            task, rows, graph = by_profile(profile)
            u0 = next(u for u in T4.units_of4(task, rows) if u["kind"] == "result" and u["linked"] and (u["outside"] == 0) == (wrong_kind == "claim_d"))
            out, res, att = self.go(task, rows, graph, script=lambda uid, n, t, u0=u0, wk=wrong_kind: compose(u0, force={"claim": wk}) if (uid == u0["unit_id"] and n == 0) else t)
            self.assertTrue(res["accepted"])
            first = next(a for a in att if a.get("unit_id") == u0["unit_id"] and a["draft"] == 1)
            self.assertIn("f", first["gates"], profile)
            self.assertFalse(first["passed"])
            self.assertEqual(C4.compare(out / res["render"] / "M23.html", task, snapshot(out))["problems"], [])

    def test_g_demonstrated_only_for_clean_data(self):
        task, rows, graph = by_profile("outside_lt")
        out, res, att = self.go(task, rows, graph, force={"study": "study_a"})
        self.assertFalse(res["accepted"])
        self.assertTrue(any("g" in a.get("gates", []) for a in att))
        task, rows, graph = by_profile("clean")
        out, res, att = self.go(task, rows, graph, force={"study": "study_a"})
        self.assertTrue(res["accepted"])
        self.assertEqual([a for a in att if "g" in a.get("gates", [])], [])

    def test_h_a_shelf_life_beyond_the_data_needs_no_blocker(self):
        task, rows, graph = by_profile("extrap")
        links = R.links_of(task)
        unit = next(u for u in T4.units_of4(task, rows) if u["kind"] == "public")
        self.assertEqual(L.gate_unit(unit, compose(unit), rows, links)[0], [])
        bad = copy.deepcopy(rows)
        key = next(g for g in links if g[0] == P.ACCEL)
        r = next(x for x in MG.group_rows(bad, *key) if x["month"] != "0")
        # an accelerated result far outside its limit: significant change for every attribute (Assay: more than 5% from month 0)
        r["value_text"] = "50.00" if key[1] == "Assay" else T4._bad_value(key[1], bad[links[key]]["value_text"])
        problems, _ = L.gate_unit(unit, compose(unit), bad, links)
        self.assertTrue(any(p.startswith("(h)") for p in problems), problems)

    def test_i_review_route_both_ways(self):
        for profile in ("outside_lt", "outside_int"):
            task, rows, graph = by_profile(profile)
            links = R.links_of(task)
            pub = next(u for u in T4.units_of4(task, rows) if u["kind"] == "public")
            self.assertTrue(pub["review"])
            good = compose(pub)
            self.assertEqual(L.gate_unit(pub, good, rows, links)[0], [])
            # a draft that proposes a shelf life (the shelf slots are not offered, and the sentence is refused whatever it says)
            shelf = "The proposed shelf life is [[shelf]] when stored at [[st_low]] to [[st_high]]. " + good
            problems, rendered = L.gate_unit(pub, shelf, rows, links)
            self.assertIsNone(rendered)
            self.assertTrue(any(p.startswith("(i)") for p in problems), problems)
            words_only = "The proposed shelf life is long. " + good
            self.assertTrue(any(p.startswith("(i)") for p in L.gate_unit(pub, words_only, rows, links)[0]))
            # the whole world: first draft proposes a shelf life, retry is clean -> accepted with the marker
            out, res, att = self.go_review(task, rows, graph, pub["unit_id"], shelf)
            self.assertTrue(res["accepted"], res)
            self.assertTrue(res["review_route"])
            first = next(a for a in att if a.get("unit_id") == "public" and a["draft"] == 1)
            self.assertIn("i", first["gates"])
            html = (out / res["render"] / "M23.html").read_text(encoding="utf-8")
            self.assertIn("HUMAN REVIEW REQUIRED: ", html)
            self.assertNotIn("proposed shelf life", html)
            self.assertIn('class="claim" data-src="M23-STAT|', html)
            self.assertEqual(C4.compare(out / res["render"] / "M23.html", task, snapshot(out))["problems"], [])

    def go_review(self, task, rows, graph, uid, bad_text):
        return self.go(task, rows, graph, script=lambda u, n, t: bad_text if (u == uid and n == 0) else t)

    def test_no_review_route_for_accelerated_only_data(self):
        for profile in ("outside_accel", "sig_assay"):
            task, rows, graph = by_profile(profile)
            unit = next(u for u in T4.units_of4(task, rows) if u["kind"] == "public")
            self.assertFalse(unit["review"])
            shelf_free = " ".join(compose(unit).split(". ")[1:])                       # a draft without the shelf sentence
            problems, _ = L.gate_unit(unit, shelf_free, rows, R.links_of(task))
            self.assertTrue(any(p.startswith("(b) missing placeholder [[shelf]]") for p in problems))   # the shelf sentence is required when there is no review
            self.assertFalse(any(p.startswith("(i)") for p in problems))

    def test_unlinked_group_has_no_claim_sentence(self):
        rows, task = G.collect(), T4.real_task4()
        units = {u["unit_id"]: u for u in T4.units_of4(task, rows)}
        u = next(x for x in units.values() if x["kind"] == "result" and x["attribute"] == "Assay")
        links = R.links_of(task)
        self.assertEqual(L.gate_unit(u, compose(u), rows, links)[0], [])
        claim = next(x for x in S.M23D_SHAPES["claim"] if x[0] == "claim_a")
        both = compose(u) + " " + compose(dict(u, expect=["claim"], outside=0))
        problems, _ = L.gate_unit(u, both, rows, links)
        self.assertTrue(any(p.startswith("(c)") and "exactly 1" in p for p in problems), problems)
        self.assertEqual(claim[3], "zero")

    def test_a_missing_limit_never_means_none_outside(self):
        rows, task = G.collect(), T4.real_task4()
        broken = copy.deepcopy(rows)
        for r in MG.group_rows(broken, P.LONG, "Assay"):
            r["limit_text"] = ""
        links = R.links_of(task)
        self.assertTrue(any("limit is unknown" in b for b in R.study_blockers(broken, links)))
        pub = next(u for u in T4.units_of4(task, broken) if u["kind"] == "public")
        self.assertEqual(pub["context"]["demonstrated"], "not allowed")
        self.assertTrue(any("R7" in p for p in T4.consistency_problems4(task, broken)))


class ComparerPlanted(unittest.TestCase):
    """The independent comparer must FAIL on each planted change of a saved file."""

    def saved(self, profile):
        task, rows, graph = by_profile(profile)
        tmp, out, res = run(task, graph, Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        self.assertTrue(res["accepted"])
        html_path = out / res["render"] / "M23.html"
        return task, snapshot(out), html_path, html_path.read_text(encoding="utf-8")

    def check(self, task, rows, html, tmp_name="x.html"):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / tmp_name
            p.write_text(html, encoding="utf-8")
            return C4.compare(p, task, rows)["problems"]

    def test_review_marker_removed_added_or_shelf_sentence_added(self):
        task, rows, path, html = self.saved("outside_lt")
        self.assertEqual(self.check(task, rows, html), [])
        no_marker = re.sub(r'<p data-section="review">.*?</p>', "", html, flags=re.S)
        self.assertTrue(self.check(task, rows, no_marker))
        shelf = html.replace('<p data-section="public">', '<p data-section="public">The proposed shelf life is long. ')
        self.assertTrue(any("shelf" in p for p in self.check(task, rows, shelf)))
        task2, rows2, path2, html2 = self.saved("clean")
        extra = html2.replace('<p data-section="public">', '<p data-section="review">HUMAN REVIEW REQUIRED: x</p><p data-section="public">')
        self.assertTrue(self.check(task2, rows2, extra))

    def test_claim_polarity_link_and_range_only(self):
        task, rows, path, html = self.saved("outside_accel")
        self.assertEqual(self.check(task, rows, html), [])
        flipped = html.replace("had results outside the limit", "had no results outside the limit")
        self.assertTrue(self.check(task, rows, flipped))
        unlinked = re.sub(r'<span class="claim" data-src="M23-STAT\|[^"]*">(.*?)</span>', r"\1", html, flags=re.S)
        self.assertTrue(self.check(task, rows, unlinked))

    def test_r7_a_changed_spec_fact_is_found(self):
        task, rows, path, html = self.saved("clean")
        bad = copy.deepcopy(rows)
        fid = next(g["spec_fact"] for g in task["results"])
        bad[fid]["value_text"] = "1.0" if bad[fid]["limit_kind"] == "NMT" else "60.0"
        self.assertTrue(any(p.startswith("R7") for p in self.check(task, bad, html)))


class MetricsAndPrompt(unittest.TestCase):
    def test_blank_makes_a_filled_menu_line_equal_to_its_pattern(self):
        task, rows, graph = by_profile("clean")
        unit = next(u for u in T4.units_of4(task, rows) if u["kind"] == "result" and u["linked"])
        menu = PR.patterns_menu(T4.view_of4(unit))
        filled = compose(unit)
        for s in RUN._sentences(filled):
            self.assertIn(RUN.blank(s), RUN.blank(menu), s)                 # the fixed metric sees the copy
            self.assertNotIn(s, menu)                                       # the old exact metric did not (a filled pattern is not a menu line)

    def test_copy_stats_counts_a_filled_pattern_as_copied(self):
        task, rows, graph = by_profile("clean")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "w"
        res = L.run_world(Scripted(task, rows), task, out, graph)               # the real prompt builder
        self.assertTrue(res["accepted"], res)
        stats = RUN.copy_stats(out / "attempts.jsonl")
        self.assertEqual(stats["whole"], 0)
        self.assertEqual(stats["sentences_copied"], 0)
        self.assertGreater(stats["blanked_sentences_copied"], 0)
        self.assertEqual(stats["blanked_sentences_copied"], stats["sentences"])

    def test_gate_stats_count_real_drafts_only_and_first_draft_pattern(self):
        task, rows, graph = by_profile("outside_accel")
        u0 = next(u for u in T4.units_of4(task, rows) if u["kind"] == "result" and u["linked"] and u["outside"])
        script = lambda uid, n, t: compose(u0, force={"claim": "claim_a"}) if (uid == u0["unit_id"] and n == 0) else t   # noqa: E731
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "w"
        res = L.run_world(Scripted(task, rows, script=script), task, out, graph)
        self.assertTrue(res["accepted"])
        st = RUN.gate_stats(out / "attempts.jsonl")
        self.assertEqual(st["fired"]["f"], 1)
        self.assertEqual(st["first_draft_wrong_pattern"], 1)
        self.assertEqual(st["fired"]["i"], 0)
        # planted drafts are not counted
        rec = out / "attempts.jsonl"
        lines = rec.read_text(encoding="utf-8").splitlines()
        planted = json.loads(lines[0])
        planted.update(planted=True, gates=["f", "g"])
        rec2 = Path(tmp.name) / "planted.jsonl"
        rec2.write_text("\n".join([json.dumps(planted)] + lines[1:]) + "\n", encoding="utf-8")
        self.assertEqual(RUN.gate_stats(rec2)["fired"]["g"], 0)

    def test_prompts_have_no_digit_and_show_every_pattern_not_only_the_true_ones(self):
        for which, n in (("dev", T4.DEV_COUNT), ("heldout", T4.HELD_COUNT)):
            for i in range(1, n + 1):
                task, rows = T4.synthetic_task4(which, i)
                for u in T4.units_of4(task, rows):
                    msgs = PR.build_messages(T4.view_of4(u))
                    self.assertFalse(re.search(r"\d", "".join(m["content"] for m in msgs)))
                    text = msgs[1]["content"]
                    for kind in dict.fromkeys(u["expect"]):
                        if kind in ("spec_intro", "spec_row"):
                            continue
                        for name, tmpl, slots, needs in S.M23D_SHAPES[kind]:
                            pat = PR._pattern(tmpl, slots, False)
                            self.assertIn(pat, text, (u["unit_id"], name))          # every pattern, whatever the data say
                    if u["kind"] == "public":
                        self.assertIn("DEMONSTRATED: " + u["context"]["demonstrated"], text)
                        self.assertIn("SHELF PROPOSAL: " + ("blocked (human review)" if u["review"] else "written"), text)
                        if u["review"]:
                            self.assertNotIn("proposed shelf life", text.split("PATTERNS")[1])
                    if u["kind"] == "result":
                        self.assertIn("OUTSIDE LIMIT: " + u["context"]["outside"], text)

    def test_no_pattern_is_a_finished_sentence_and_study_has_four(self):
        self.assertEqual(len(S.M23D_SHAPES["study"]), 4)
        self.assertEqual([x[0] for x in S.M23D_SHAPES["study"]], ["study_a", "study_b", "study_n", "study_o"])
        names = {"test": ["Assay"], "kind": ["NLT"], "attr": ["Assay"], "cond": ["long-term"]}
        for kind, shapes in S.M23D_SHAPES.items():
            for name, tmpl, slots, needs in shapes:
                if kind == "spec_intro":                      # its menu lines are PR.INTRO_PATTERNS (blanks word-a / word-b), tested below
                    continue
                pat = PR._pattern(tmpl, slots, False)
                self.assertIn("<", pat)
                self.assertIsNone(S.m23d_classify(pat, names), name)
        for pat in PR.INTRO_PATTERNS:
            self.assertIn("<", pat)
            self.assertIsNone(S.m23d_classify(pat, names))

    def test_the_trimmed_set_still_classifies_every_filled_pattern(self):
        names = {"test": ["Assay"], "kind": ["NLT"], "attr": ["Assay"], "cond": ["long-term"]}
        for kind, shapes in S.M23D_SHAPES.items():
            for name, tmpl, slots, needs in shapes:
                done = PH_FIELD.sub(lambda m: {"s": "5%", "attr": "Assay", "cond": "long-term", "test": "Assay", "kind": "NLT"}[m.group(1)], tmpl)
                got = S.m23d_classify(done, names)
                self.assertIsNotNone(got, name)
                self.assertEqual(got[1], name)
        long_form = "Long-term stability was demonstrated for 5 months, and accelerated stability for 5 months."
        self.assertIsNone(S.m23d_classify(long_form.replace("5 months", "5 months"), {}, kinds=("study",)))      # study_c is gone from the fourth set


if __name__ == "__main__":
    unittest.main()
