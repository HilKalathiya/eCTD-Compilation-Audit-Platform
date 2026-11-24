"""Tests for the T-073 2.3 writer: clean controls, one limit source (R7), "demonstrated" and extrapolation rules each planted both ways, claim links, the independent comparer."""
import copy
import json
import re
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ectd_engine.graph import summary_graph as G
from ectd_engine.review import shapes as S
from ectd_engine.summary import m23_compare3 as C3
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import m23_loop3 as L
from ectd_engine.summary import m23_rules as R
from ectd_engine.summary import m23_tasks3 as T3
from ectd_engine.summary import plan as P

PH_FIELD = re.compile(r"\{(s|test|attr|cond|kind)\}")
ROOT = Path(__file__).resolve().parent.parent


def stub_messages(view, feedback):
    return [{"role": "user", "content": json.dumps({"view": view, "feedback": feedback})}]


class FakeGraph:
    namespace = "TEST"

    def __init__(self, rows):
        self._rows = rows

    def rows(self):
        return copy.deepcopy(self._rows)


def compose(unit, choice=None, force=None):
    """The correct draft for a unit in the wording chosen per sentence kind. force = {kind: shape name} picks one wording whatever its tag."""
    choice, force, lines = choice or {}, force or {}, []
    for j, kind in enumerate(unit["expect"]):
        shapes = S.M23C_SHAPES[kind]
        if kind == "claim":
            shapes = [x for x in shapes if x[3] == ("zero" if unit["outside"] == 0 else "some")]
        if kind == "study" and unit["study_blockers"]:
            shapes = [x for x in shapes if x[3] is None]
        name, template, slots, _ = next((x for x in S.M23C_SHAPES[kind] if x[0] == force[kind]), None) if kind in force else shapes[choice.get(kind, 0) % len(shapes)]
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
        self.units = {u["unit_id"]: u for u in T3.units_of3(task, rows)}
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
    task, rows = T3.synthetic_task3(which, i)
    return task, rows, MG.MemoryGraph(rows)


def run(task, graph, client, **kw):
    tmp = tempfile.TemporaryDirectory()
    out = Path(tmp.name) / "w"
    res = L.run_world(client, task, out, graph, build_messages=stub_messages, **kw)
    return tmp, out, res


def by_profile(which, profile):
    return next(synthetic(which, i) for i in range(1, 11) if T3.PROFILES[i - 1] == profile)


def bad_assay_at_long_term(rows):
    """A copy of the rows in which one long-term Assay-or-other result is outside its limit (the first group at the long-term condition)."""
    rows = copy.deepcopy(rows)
    cond, attr = next(g for g in R.groups_in(rows) if g[0] == P.LONG)
    r = next(x for x in rows.values() if x["family"] == "stability" and x["kind"] == "demo" and x["condition"] == cond and x["attribute"] == attr
             and x["month"] != "0")
    r["value_text"] = {"Assay": "94.50", "Degradation product": "0.520"}.get(attr, "10.00")
    return rows


class Control(unittest.TestCase):
    def test_every_task_passes_all_gates_and_the_independent_comparer(self):
        for which, n in (("dev", T3.DEV_COUNT), ("heldout", T3.HELD_COUNT)):
            for i in range(1, n + 1):
                task, rows, graph = synthetic(which, i)
                tmp, out, res = run(task, graph, Scripted(task, rows))
                self.addCleanup(tmp.cleanup)
                self.assertTrue(res["accepted"], (task["task_id"], res))
                self.assertEqual(set(res["drafts"].values()), {1})
                cmp_ = C3.compare(out / res["render"] / "M23.html", task, json.loads((out / "graph_snapshot_check.json").read_text(encoding="utf-8")))
                self.assertEqual(cmp_["problems"], [], task["task_id"])

    def test_the_real_task_renders_from_a_graph_and_passes(self):
        rows, task = G.collect(), T3.real_task3()
        tmp, out, res = run(task, FakeGraph(rows), Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        self.assertTrue(res["accepted"], res)
        for fmt in ("html", "docx"):
            c = res["counts"][fmt]
            self.assertEqual((c["failed"], c["uncovered"], c["checked"] - c["matched"]), (0, 0, 0))
        self.assertEqual(C3.compare(out / "render_1" / "M23.html", task, rows)["problems"], [])

    def test_every_wording_of_every_sentence_kind_passes(self):
        task, rows, graph = synthetic("dev", 2)                      # a clean, extrapolating task: every study wording is allowed
        for k in range(max(len(v) for v in S.M23C_SHAPES.values())):
            tmp, out, res = run(task, graph, Scripted(task, rows, choice={kind: k for kind in S.M23C_SHAPES}))
            self.addCleanup(tmp.cleanup)
            self.assertTrue(res["accepted"], (k, res))

    def test_claim_links_are_in_the_html_and_never_in_the_placements(self):
        task, rows, graph = by_profile("dev", "extrap")
        tmp, out, res = run(task, graph, Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        html = (out / res["render"] / "M23.html").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'<span class="claim" data-src="[^"]*outside_limit_count[^"]*">', html)), len(task["results"]) + 2)   # claims + study + shelf
        self.assertIn("significant_change", html)
        for line in (out / res["render"] / "placements.jsonl").read_text(encoding="utf-8").splitlines():
            self.assertNotIn("outside_limit_count", line)
            self.assertNotIn("significant_change", line)


class OneLimitSource(unittest.TestCase):
    def test_the_t072_held_19_mismatch_is_flagged_by_r7(self):
        d = ROOT / "evidence" / "T-072" / "tasks" / "heldout"
        task = json.loads(next(d.glob("*19.json")).read_text(encoding="utf-8"))
        rows = json.loads((d / task["graph_file"]).read_text(encoding="utf-8"))["rows"]
        self.assertTrue(any(p.startswith("R7") and "75" in p for p in R.limit_problems(rows)), R.limit_problems(rows))

    def test_a_changed_spec_value_is_refused_before_any_draft(self):
        task, rows, _ = by_profile("dev", "clean")
        rows = copy.deepcopy(rows)
        sid = G.spec_id("dissolution_av")
        dissolved = [g for g in task["results"] if g["attribute"] == "Dissolution (15 min)"]
        if not dissolved:
            task, rows, _ = next(synthetic("dev", i) for i in range(1, 11) if any(g["attribute"] == "Dissolution (15 min)" for g in synthetic("dev", i)[0]["results"]))
            rows = copy.deepcopy(rows)
        rows[sid]["value_text"] = str(Decimal(rows[sid]["value_text"]) + 5)
        self.assertTrue(any(p.startswith("R7") for p in T3.consistency_problems3(task, rows)))
        tmp, out, res = run(task, MG.MemoryGraph(rows), Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        self.assertFalse(res["accepted"])
        self.assertIn("R7", res["reason"])
        self.assertFalse((out / "attempts.jsonl").exists())

    def test_the_spec_fact_must_be_shown_in_the_table(self):
        task, rows, _ = next(synthetic("dev", i) for i in range(1, 11) if any(g["attribute"] == "Dissolution (15 min)" for g in synthetic("dev", i)[0]["results"]))
        task = copy.deepcopy(task)
        task["spec"] = [s for s in task["spec"] if s["attribute"] != "dissolution_av"]
        self.assertTrue(any("does not show" in p for p in T3.consistency_problems3(task, rows)))

    def test_the_count_follows_the_spec_fact_not_the_rows(self):
        task, rows, _ = next(synthetic("dev", i) for i in range(1, 11) if any(g["attribute"] == "Dissolution (15 min)" for g in synthetic("dev", i)[0]["results"]))
        sid = G.spec_id("dissolution_av")
        rows = copy.deepcopy(rows)
        rows[sid]["value_text"] = "99"                                      # every stored dissolution result is now below NLT 99
        self.assertGreater(R.outside_count(rows, P.LONG, "Dissolution (15 min)"), 0)
        self.assertEqual(MG.stats(rows, P.LONG, "Dissolution (15 min)")["outside"], 0)   # the old, row-limit reader would still say 0

    def test_the_real_task_has_one_limit_source(self):
        self.assertEqual(R.limit_problems(G.collect()), [])


class Demonstrated(unittest.TestCase):
    def gate(self, task, rows, force):
        units = {u["unit_id"]: u for u in T3.units_of3(task, rows)}
        return L.gate_unit(units["public"], compose(units["public"], force=force), rows)

    def test_demonstrated_is_refused_when_a_long_term_result_is_outside(self):
        task, rows, _ = by_profile("dev", "outside_lt")
        for shape in ("study_a", "study_c"):
            problems, _ = self.gate(task, rows, {"study": shape})
            self.assertTrue(any(p.startswith("(g)") for p in problems), (shape, problems))

    def test_a_neutral_study_sentence_is_always_allowed(self):
        task, rows, _ = by_profile("dev", "outside_lt")
        for shape in ("study_b", "study_n", "study_o"):
            self.assertEqual(self.gate(task, rows, {"study": shape})[0], [], shape)

    def test_demonstrated_is_allowed_on_clean_data_and_when_only_accelerated_is_outside(self):
        for profile in ("clean", "extrap", "sig_assay", "outside_accel"):
            task, rows, _ = by_profile("dev", profile)
            for shape in ("study_a", "study_c"):
                self.assertEqual(self.gate(task, rows, {"study": shape})[0], [], (profile, shape))

    def test_the_gate_follows_the_rows_at_gate_time(self):
        task, rows, _ = by_profile("dev", "clean")
        units = {u["unit_id"]: u for u in T3.units_of3(task, rows)}
        text = compose(units["public"], force={"study": "study_a"})
        self.assertEqual(L.gate_unit(units["public"], text, rows)[0], [])
        self.assertTrue(any(p.startswith("(g)") for p in L.gate_unit(units["public"], text, bad_assay_at_long_term(rows))[0]))

    def test_a_world_that_always_says_demonstrated_is_rejected_on_bad_data(self):
        task, rows, graph = by_profile("dev", "outside_lt")
        tmp, out, res = run(task, graph, Scripted(task, rows, force={"study": "study_a"}))
        self.addCleanup(tmp.cleanup)
        self.assertFalse(res["accepted"])
        self.assertIn("public", res["reason"])

    def test_no_long_term_result_means_no_demonstrated(self):
        task, rows, _ = by_profile("dev", "clean")
        rows = {k: v for k, v in rows.items() if not (v["family"] == "stability" and v["kind"] == "demo" and v["condition"] == P.LONG)}
        self.assertTrue(R.study_blockers(rows))


class Extrapolation(unittest.TestCase):
    def test_a_clean_extrapolating_task_is_consistent_and_its_shelf_is_beyond_the_data(self):
        task, rows, _ = by_profile("dev", "extrap")
        self.assertTrue(task["extrapolation"])
        self.assertEqual(R.extrapolation_blockers(rows), [])
        self.assertEqual(T3.consistency_problems3(task, rows), [])

    def test_each_blocker_refuses_the_extrapolation(self):
        task, rows, _ = by_profile("dev", "extrap")
        cases = {"a long-term result outside the limit": (task, bad_assay_at_long_term(rows))}
        no_accel = {k: v for k, v in rows.items() if not (v["family"] == "stability" and v["kind"] == "demo" and v["condition"] == P.ACCEL)}
        cases["no accelerated data"] = (dict(task, results=[g for g in task["results"] if g["condition"] != P.ACCEL]), no_accel)
        drift = copy.deepcopy(rows)
        for r in drift.values():
            if r["family"] == "stability" and r["kind"] == "demo" and r["condition"] == P.ACCEL and r["attribute"] == "Assay":
                r["value_text"] = "100.00" if r["month"] == "0" else "94.00"
        if any(a == "Assay" and c == P.ACCEL for c, a in R.groups_in(rows)):
            cases["significant change in assay"] = (task, drift)
        self.assertGreaterEqual(len(cases), 2)
        for name, (t, bad) in cases.items():
            self.assertTrue(any(p.startswith("R8") for p in T3.consistency_problems3(t, bad)), name)
            tmp, out, res = run(t, MG.MemoryGraph(bad), Scripted(t, bad))
            self.addCleanup(tmp.cleanup)
            self.assertFalse(res["accepted"], name)
            self.assertIn("R8", res["reason"], name)

    def test_the_generator_refused_extrapolation_where_the_data_forbid_it(self):
        for which in ("dev", "heldout"):
            n = T3.DEV_COUNT if which == "dev" else T3.HELD_COUNT
            for i in range(1, n + 1):
                task, rows = T3.synthetic_task3(which, i)
                if task["extrapolation_refused"]:
                    self.assertIsNone(task["extrapolation"])
                    self.assertTrue(task["extrapolation_refused"]["reasons"])
                    # the same task asked for the longer shelf life is refused by R8
                    wanted = task["extrapolation_refused"]["wanted_months"]
                    longer = copy.deepcopy(rows)
                    longer[task["public"]["shelf"]["fact_id"]]["value_text"] = str(wanted)
                    ex = G.stab_id("extrapolation", "extrapolation_to_months", wanted)
                    longer[ex] = dict(longer[task["public"]["shelf"]["fact_id"]], fact_id=ex, attribute="extrapolation_to_months", value_text=str(wanted))
                    ask = dict(task, extrapolation=ex)
                    self.assertTrue(any(p.startswith("R8") for p in T3.consistency_problems3(ask, longer)), task["task_id"])

    def test_the_gate_h_follows_the_rows(self):
        task, rows, _ = by_profile("dev", "extrap")
        units = {u["unit_id"]: u for u in T3.units_of3(task, rows)}
        text = compose(units["public"])
        self.assertEqual(L.gate_unit(units["public"], text, rows)[0], [])
        problems = L.gate_unit(units["public"], text, bad_assay_at_long_term(rows))[0]
        self.assertTrue(any(p.startswith("(h)") for p in problems), problems)

    def test_the_significant_change_boundary_for_assay_is_five_percent_or_more(self):
        def rows_with(v):
            return {"a": {"family": "stability", "kind": "demo", "condition": P.ACCEL, "attribute": "Assay", "month": "0", "value_text": "100.00", "limit_text": "95.0-105.0"},
                    "b": {"family": "stability", "kind": "demo", "condition": P.ACCEL, "attribute": "Assay", "month": "3", "value_text": v, "limit_text": "95.0-105.0"}}
        self.assertTrue(R.significant_change(rows_with("95.00"), "Assay"))        # exactly 5% change
        self.assertFalse(R.significant_change(rows_with("95.01"), "Assay"))       # just below
        self.assertTrue(R.significant_change(rows_with("105.00"), "Assay"))       # a rise counts as well
        self.assertFalse(R.significant_change(rows_with("104.99"), "Assay"))
        self.assertTrue(C3._significant(rows_with("95.00"), "Assay"))             # the comparer's own code agrees at the boundary
        self.assertFalse(C3._significant(rows_with("95.01"), "Assay"))

    def test_significant_change_without_a_result_outside_the_limit_is_its_own_blocker(self):
        task, rows, _ = by_profile("dev", "sig_assay")
        self.assertTrue(all(R.outside_count(rows, c, a) == 0 for c, a in R.groups_in(rows)))
        self.assertTrue(R.significant_change(rows, "Assay"))
        self.assertTrue(task["extrapolation_refused"])

    def test_a_result_exactly_on_the_limit_is_inside(self):
        rows = {"a": {"family": "stability", "kind": "demo", "condition": P.LONG, "attribute": "Degradation product", "month": "3", "value_text": "0.500", "limit_text": "NMT 0.50"},
                "b": {"family": "stability", "kind": "demo", "condition": P.LONG, "attribute": "Degradation product", "month": "6", "value_text": "0.501", "limit_text": "NMT 0.50"}}
        self.assertEqual(R.outside_count(rows, P.LONG, "Degradation product"), 1)


class IndependentComparer(unittest.TestCase):
    def render(self, profile):
        task, rows, graph = by_profile("dev", profile)
        tmp, out, res = run(task, graph, Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        html = (out / res["render"] / "M23.html").read_text(encoding="utf-8")
        return task, rows, html, tmp

    def check(self, task, rows, html):
        p = Path(tempfile.mkdtemp()) / "x.html"
        p.write_text(html, encoding="utf-8")
        return C3.compare(p, task, rows)["problems"]

    def test_a_planted_demonstrated_on_bad_data_is_found(self):
        task, rows, html, _ = self.render("outside_lt")
        self.assertEqual(self.check(task, rows, html), [])
        planted = html.replace("Stability data cover", "Stability was demonstrated for") if "Stability data cover" in html else html.replace(
            "Data are available for", "Stability was demonstrated for").replace("Long-term data are available for", "Long-term stability was demonstrated for")
        self.assertNotEqual(planted, html)
        self.assertTrue(any("demonstrated" in p for p in self.check(task, rows, planted)))

    def test_a_missing_claim_link_is_found(self):
        task, rows, html, _ = self.render("extrap")
        stripped = re.sub(r'<span class="claim" data-src="[^"]*">(.*?)</span>(?=</p>)', r"\1", html, count=1)
        self.assertEqual(self.check(task, rows, html), [])
        self.assertNotEqual(stripped, html)
        self.assertTrue(self.check(task, rows, re.sub(r'<span class="claim" data-src="M23-STAT\|[^"]*significant_change[^"]*">', '<span class="claim" data-src="">', html)))

    def test_a_wrong_polarity_claim_is_found(self):
        task, rows, html, _ = self.render("outside_lt")
        self.assertIn("had results outside the limit", html)
        self.assertTrue(self.check(task, rows, html.replace("had results outside the limit", "had no results outside the limit")))

    def test_the_comparer_finds_a_limit_that_differs_from_the_spec_table(self):
        task, rows, html, _ = self.render("clean")
        rows = copy.deepcopy(rows)
        for r in rows.values():
            if r["family"] == "stability" and r["kind"] == "demo" and r["attribute"] == "Dissolution (15 min)":
                r["limit_text"] = "NLT 1"
        if any(r["attribute"] == "Dissolution (15 min)" for r in rows.values()):
            self.assertTrue(any(p.startswith("R7") for p in self.check(task, rows, html)))


if __name__ == "__main__":
    unittest.main()
