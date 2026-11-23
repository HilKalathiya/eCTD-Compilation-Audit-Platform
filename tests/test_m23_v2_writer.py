"""Tests for the T-072 2.3 writer: clean controls in every wording, one-defect planted drafts, the cross-fact gate both ways, graph-sourced numbers, crosscheck per wording."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ectd_engine.graph import facts_graph
from ectd_engine.graph import summary_graph as G
from ectd_engine.review import shapes as S
from ectd_engine.summary import crosscheck as X
from ectd_engine.summary import m23_graph as MG
from ectd_engine.summary import m23_loop2 as L
from ectd_engine.summary import m23_tasks2 as T
from ectd_engine.summary import plan as P

PH_FIELD = re.compile(r"\{(s|test|attr|cond|kind)\}")


def stub_messages(view, feedback):
    return [{"role": "user", "content": json.dumps({"view": view, "feedback": feedback})}]


class FakeGraph:
    """A graph made of ready rows (used to render the REAL task without Neo4j in a test)."""
    namespace = "TEST"

    def __init__(self, rows):
        self._rows = rows

    def rows(self):
        return copy.deepcopy(self._rows)


def compose(unit, choice=None):
    """The correct draft for a unit, in the wording chosen per sentence kind (index into M23B_SHAPES[kind], default 0)."""
    choice = choice or {}
    lines = []
    for j, kind in enumerate(unit["expect"]):
        shapes = S.M23B_SHAPES[kind]
        name, template, slots, _ = shapes[choice.get(kind, 0) % len(shapes)]
        if kind == "claim":
            ok = [x for x in shapes if x[3] == ("zero" if unit["outside"] == 0 else "some")]
            name, template, slots, _ = ok[choice.get("claim", 0) % len(ok)]
        plain = iter([s for s in slots if s != "attr"])

        def sub(m):
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
    """A fake model: script(unit_id, draft_number, perfect_text) -> text; default = the correct draft in the wording given by `choice`."""

    def __init__(self, task, rows, script=None, choice=None):
        self.units = {u["unit_id"]: u for u in T.units_of(task, rows)}
        self.script, self.choice, self.calls, self.seen = script, choice, {}, []

    def chat(self, messages, temperature, seed, context=None, schema=None):
        uid = context["unit_id"]
        n = self.calls.get(uid, 0)
        self.calls[uid] = n + 1
        self.seen.append((uid, n, messages, seed, temperature))
        text = compose(self.units[uid], self.choice)
        if self.script:
            text = self.script(uid, n, text)
        return {"text": text, "seconds": 0.0, "output_tokens": 0}


def synthetic(which, i):
    task, rows = T.synthetic_task(which, i)
    return task, rows, MG.MemoryGraph(rows)


def run(task, graph, client, **kw):
    tmp = tempfile.TemporaryDirectory()
    out = Path(tmp.name) / "w"
    res = L.run_world(client, task, out, graph, build_messages=stub_messages, **kw)
    return tmp, out, res


def unit_of(units, kind, **flt):
    return next(u for u in units if u["kind"] == kind and all(u.get(k) == v for k, v in flt.items()))


class Control(unittest.TestCase):
    def test_every_task_passes_all_gates_with_no_retry(self):
        for which, n in (("dev", T.DEV_COUNT), ("heldout", T.HELD_COUNT)):
            for i in range(1, n + 1):
                task, rows, graph = synthetic(which, i)
                tmp, out, res = run(task, graph, Scripted(task, rows))
                self.addCleanup(tmp.cleanup)
                self.assertTrue(res["accepted"], (task["task_id"], res))
                self.assertEqual(set(res["drafts"].values()), {1})

    def test_the_real_task_renders_from_a_graph_and_passes(self):
        rows = G.collect()
        task = T.real_task()
        tmp, out, res = run(task, FakeGraph(rows), Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        self.assertTrue(res["accepted"], res)
        for fmt in ("html", "docx"):
            c = res["counts"][fmt]
            self.assertEqual((c["failed"], c["uncovered"], c["checked"] - c["matched"]), (0, 0, 0))
        html = (out / "render_1" / "M23.html").read_text(encoding="utf-8")
        self.assertIn("Dissolution (", html)              # the time point stays in the name (T-072 item 6)
        self.assertNotIn("synthetic", html)

    def test_every_wording_of_every_sentence_kind_passes_gates_and_crosscheck(self):
        task, rows, graph = synthetic("dev", 1)
        longest = max(len(v) for v in S.M23B_SHAPES.values())
        for k in range(longest):
            tmp, out, res = run(task, graph, Scripted(task, rows, choice={kind: k for kind in S.M23B_SHAPES}))
            self.addCleanup(tmp.cleanup)
            self.assertTrue(res["accepted"], (k, res))

    def test_a_run_folder_is_never_overwritten(self):
        task, rows, graph = synthetic("dev", 1)
        tmp, out, res = run(task, graph, Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        with self.assertRaises(FileExistsError):
            L.run_world(Scripted(task, rows), task, out, graph, build_messages=stub_messages)


class Planted(unittest.TestCase):
    """Each planted draft = the correct draft with exactly ONE defect; the gate meant to catch it must fire and the world must be rejected unrendered."""

    @classmethod
    def setUpClass(cls):
        # a synthetic task where shelf life = long-term months, with an outside-limit group, a clean group and a dissolution group
        for i in range(1, T.DEV_COUNT + 1):
            task, rows = T.synthetic_task("dev", i)
            units = T.units_of(task, rows)
            res = [u for u in units if u["kind"] == "result"]
            pub = {k: rows[v["fact_id"]]["value_text"] for k, v in task["public"].items()}
            if pub["shelf"] == pub["long"] and any(u["outside"] for u in res) and any(not u["outside"] for u in res) and any(u["has_tp"] for u in res):
                cls.task, cls.rows, cls.units = task, rows, units
                return
        raise AssertionError("no dev task has all the planted-test ingredients")

    def unit(self, kind, **flt):
        return unit_of(self.units, kind, **flt)

    def defect_world(self, unit, mutate):
        def script(uid, n, text):
            return mutate(text) if uid == unit["unit_id"] else text
        graph = MG.MemoryGraph(self.rows)
        tmp, out, res = run(self.task, graph, Scripted(self.task, self.rows, script))
        self.addCleanup(tmp.cleanup)
        attempts = [json.loads(x) for x in (out / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
        return res, attempts, out

    def assert_rejected_by(self, unit, mutate, gate):
        control, _ = L.gate_unit(unit, compose(unit), self.rows)
        self.assertEqual(control, [], "the control must pass")
        problems, _ = L.gate_unit(unit, mutate(compose(unit)), self.rows)
        self.assertTrue(any(p.startswith(f"({gate})") for p in problems), problems)
        res, attempts, out = self.defect_world(unit, mutate)
        self.assertFalse(res["accepted"])
        self.assertEqual(res["drafts"][unit["unit_id"]], L.MAX_DRAFTS)
        self.assertTrue(all(not a["passed"] for a in attempts if a.get("unit_id") == unit["unit_id"]))
        self.assertFalse((out / "render_1").exists(), "a rejected unit must never reach rendering")
        return problems

    def result_unit(self, tp=False, outside=False):
        return next(u for u in self.units if u["kind"] == "result" and u["has_tp"] == tp and bool(u["outside"]) == outside)

    def test_a_digit(self):
        u = self.result_unit()
        self.assert_rejected_by(u, lambda t: t.replace("[[high]].", "[[high]] in 3 batches.", 1), "a")

    def test_a_number_word(self):
        u = self.result_unit()
        p = self.assert_rejected_by(u, lambda t: t.replace("[[high]].", "[[high]] across three batches.", 1), "a")
        self.assertTrue(any("number word" in x for x in p))

    def test_a_degree_sign(self):
        self.assert_rejected_by(self.unit("public"), lambda t: t.replace("[[st_low]]", "[[st_low]]°", 1), "a")

    def test_unknown_slot(self):
        u = self.result_unit()
        p = self.assert_rejected_by(u, lambda t: t.replace("[[high]]", "[[maximum]]"), "b")
        self.assertTrue(any("not in the FACTS list" in x for x in p))

    def test_missing_required_slot(self):
        u = self.result_unit()
        p = self.assert_rejected_by(u, lambda t: re.sub(r" (to|and) \[\[high\]\]", "", t), "b")
        self.assertTrue(any("missing placeholder [[high]]" in x for x in p))

    def test_a_slot_used_in_the_wrong_place_twice_over(self):
        u = self.result_unit()
        self.assert_rejected_by(u, lambda t: t.replace("[[high]]", "[[low]]"), "b")

    def test_the_dissolution_time_point_slot_cannot_be_left_out(self):
        u = self.result_unit(tp=True)
        p = self.assert_rejected_by(u, lambda t: t.replace(" ([[tp]])", ""), "b")
        self.assertTrue(any("[[tp]]" in x for x in p))

    def test_shelf_life_slot_used_as_storage(self):
        swap = lambda t: t.replace("[[shelf]]", "[[@]]").replace("[[st_low]]", "[[shelf]]").replace("[[@]]", "[[st_low]]")  # noqa: E731
        res, _, _ = self.defect_world(self.unit("public"), swap)
        problems, _ = L.gate_unit(self.unit("public"), swap(compose(self.unit("public"))), self.rows)
        self.assertTrue(problems)
        self.assertFalse(res["accepted"])

    def test_coincident_values_swapped_between_places_are_caught_by_the_slot_binding(self):
        u = self.unit("public")
        swap = lambda t: t.replace("[[shelf]]", "[[@]]").replace("[[long]]", "[[shelf]]").replace("[[@]]", "[[long]]")  # noqa: E731
        render = lambda text: [re.sub(r"\[\[(\w+)\]\]", lambda m: u["slots"][m.group(1)]["text"], s) for s in L.split_draft(u, text)]  # noqa: E731
        self.assertEqual(render(compose(u)), render(swap(compose(u))), "the swap must be invisible to a value check")
        p = self.assert_rejected_by(u, swap, "b")
        self.assertTrue(any("each value belongs to its own place" in x for x in p))

    def test_demo_label_dropped(self):
        self.assert_rejected_by(self.result_unit(), lambda t: t.replace("In illustrative demonstration data, ", "", 1), "c")

    def test_demo_label_added_to_a_public_sentence(self):
        self.assert_rejected_by(self.unit("public"), lambda t: "In illustrative demonstration data, " + t[0].lower() + t[1:], "c")

    def test_overclaim_sentence(self):
        p = self.assert_rejected_by(self.result_unit(), lambda t: t + " This fully demonstrates stability.", "c")
        self.assertTrue(any(x.startswith("(e)") for x in p), "the vocabulary gate must fire on its own as well")

    def test_extra_citation_not_in_the_registry(self):
        self.assert_rejected_by(self.result_unit(), lambda t: t.replace("[[high]].", "[[high]] (ICH Q99).", 1), "a")

    def test_a_citation_that_is_in_the_registry_is_still_not_allowed_in_a_draft(self):
        self.assert_rejected_by(self.result_unit(), lambda t: t.replace("[[high]].", "[[high]] (ICH Q3B(R2)).", 1), "a")

    def test_a_sentence_of_unknown_shape(self):
        self.assert_rejected_by(self.unit("public"), lambda t: "The product is widely accepted. " + t, "c")

    def test_spec_row_with_the_wrong_test_name(self):
        u = self.unit("spec")
        t0, t1 = u["rows"][0][0], u["rows"][1][0]
        self.assert_rejected_by(u, lambda t: t.replace(f"{t0}: ", "@@").replace(f"{t1}: ", f"{t0}: ").replace("@@", f"{t1}: "), "c")

    def test_a_period_after_a_spec_row_is_refused(self):
        self.assert_rejected_by(self.unit("spec"), lambda t: t.replace("]]", "]].", 1), "c")


class CrossFactGate(unittest.TestCase):
    """The claim sentence depends on the graph's outside-limit count: all four cases, at gate level and for the whole world."""

    @classmethod
    def setUpClass(cls):
        for i in range(1, T.DEV_COUNT + 1):
            task, rows = T.synthetic_task("dev", i)
            units = T.units_of(task, rows)
            res = [u for u in units if u["kind"] == "result"]
            if any(u["outside"] for u in res) and any(not u["outside"] for u in res):
                cls.task, cls.rows, cls.units = task, rows, units
                cls.zero = next(u for u in res if not u["outside"])
                cls.some = next(u for u in res if u["outside"])
                return
        raise AssertionError("no dev task has both kinds of group")

    def claim(self, unit, shape_name):
        """The unit's correct range sentence followed by the named claim wording (so the claim can be true or false for this unit)."""
        shape = next(s for s in S.M23B_SHAPES["claim"] if s[0] == shape_name)
        fields = {"attr": unit["attr_template"], "cond": unit["names"]["cond"][0]}
        new = re.sub(r"\{(attr|cond)\}", lambda m: fields[m.group(1)], shape[1])
        return " ".join([L.split_draft(unit, compose(unit))[0], new])

    def test_claim_none_with_a_count_of_zero_passes(self):
        for name in ("claim_a", "claim_b", "claim_c"):
            self.assertEqual(L.gate_unit(self.zero, self.claim(self.zero, name), self.rows)[0], [], name)

    def test_claim_none_with_a_count_above_zero_is_rejected_by_gate_f(self):
        for name in ("claim_a", "claim_b", "claim_c"):
            problems, _ = L.gate_unit(self.some, self.claim(self.some, name), self.rows)
            self.assertTrue(any(p.startswith("(f)") for p in problems), (name, problems))

    def test_claim_some_with_a_count_of_zero_is_rejected_by_gate_f(self):
        problems, _ = L.gate_unit(self.zero, self.claim(self.zero, "claim_d"), self.rows)
        self.assertTrue(any(p.startswith("(f)") for p in problems), problems)

    def test_claim_some_with_a_count_above_zero_passes(self):
        self.assertEqual(L.gate_unit(self.some, self.claim(self.some, "claim_d"), self.rows)[0], [])

    def test_the_count_is_read_from_the_graph_at_gate_time_not_from_the_unit(self):
        text = self.claim(self.zero, "claim_a")
        self.assertEqual(L.gate_unit(self.zero, text, self.rows)[0], [])
        changed = copy.deepcopy(self.rows)
        first = MG.group_rows(changed, self.zero["condition"], self.zero["attribute"])[0]
        first["value_text"] = {"Assay": "50.00", "Degradation product": "9.000", "Dissolution (15 min)": "10.00"}[self.zero["attribute"]]
        self.assertEqual(self.zero["outside"], 0)                               # the unit still says 0 ...
        problems, _ = L.gate_unit(self.zero, text, changed)                      # ... but the graph now has a result outside the limit
        self.assertTrue(any(p.startswith("(f)") for p in problems), problems)

    def test_a_world_that_always_claims_none_for_a_group_with_results_outside_is_rejected(self):
        def script(uid, n, text):
            if uid == self.some["unit_id"]:
                return self.claim(self.some, "claim_a")
            return text
        tmp, out, res = run(self.task, MG.MemoryGraph(self.rows), Scripted(self.task, self.rows, script))
        self.addCleanup(tmp.cleanup)
        self.assertFalse(res["accepted"])
        self.assertIn(self.some["unit_id"], res["reason"])
        self.assertFalse((out / "render_1").exists())


class GraphIsTheSource(unittest.TestCase):
    def test_a_changed_graph_value_changes_the_rendered_number(self):
        task, rows, _ = synthetic("dev", 1)
        shelf_id = task["public"]["shelf"]["fact_id"]
        was = rows[shelf_id]["value_text"]
        changed = copy.deepcopy(rows)
        changed[shelf_id]["value_text"] = str(int(was) + 1)
        tmp, out, res = run(task, MG.MemoryGraph(changed), Scripted(task, changed))     # the task file is the same; only the graph differs
        self.addCleanup(tmp.cleanup)
        html = (out / "graph_snapshot.json").read_text(encoding="utf-8")
        self.assertIn(f'"value_text": "{int(was) + 1}"', html)
        if res["accepted"]:
            page = (out / "render_1" / "M23.html").read_text(encoding="utf-8")
            self.assertIn(f">{int(was) + 1}</span> months when stored", page)

    def test_the_cross_check_read_must_equal_the_render_read(self):
        task, rows, graph = synthetic("dev", 1)
        other = copy.deepcopy(rows)
        other[task["public"]["shelf"]["fact_id"]]["value_text"] = "1"
        client = Scripted(task, rows)
        tmp, out, res = run(task, graph, client, check_rows=other)
        self.addCleanup(tmp.cleanup)
        self.assertFalse(res["accepted"])
        self.assertIn("not the same", res["reason"])
        self.assertEqual(client.calls, {}, "no draft may be asked when the two graph reads differ")

    def test_the_real_task_renders_with_the_csv_build_broken(self):
        rows = G.collect()
        graph = FakeGraph(rows)
        task = T.real_task()
        with mock.patch.object(G, "collect", side_effect=AssertionError("the render path must not call G.collect")):
            tmp, out, res = run(task, graph, Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        self.assertTrue(res["accepted"], res)

    def test_a_synthetic_run_never_opens_neo4j(self):
        task, rows, graph = synthetic("dev", 2)
        with mock.patch.object(facts_graph, "connect", side_effect=AssertionError("a synthetic run must never open Neo4j")):
            tmp, out, res = run(task, graph, Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        self.assertTrue(res["accepted"], res)

    def test_an_inconsistent_task_is_refused_before_any_draft_is_asked(self):
        task, rows = T.synthetic_task("dev", 1)
        bad = copy.deepcopy(rows)
        bad[task["public"]["shelf"]["fact_id"]]["value_text"] = str(int(bad[task["public"]["long"]["fact_id"]]["value_text"]) + 6)
        client = Scripted(task, rows)
        tmp, out, res = run(task, MG.MemoryGraph(bad), client)
        self.addCleanup(tmp.cleanup)
        self.assertFalse(res["accepted"])
        self.assertTrue(res["reason"].startswith("task is not self-consistent"), res["reason"])
        self.assertEqual(client.calls, {})

    def test_the_saved_snapshots_hold_the_rows_used(self):
        task, rows, graph = synthetic("dev", 1)
        tmp, out, res = run(task, graph, Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        a = json.loads((out / "graph_snapshot.json").read_text(encoding="utf-8"))
        b = json.loads((out / "graph_snapshot_check.json").read_text(encoding="utf-8"))
        self.assertEqual(a, b)
        self.assertEqual(a, rows)


class CrosscheckWordings(unittest.TestCase):
    """The cross-check knows every allowed wording; a number in the wrong place still fails in each of them, even when two values are equal."""

    @classmethod
    def setUpClass(cls):
        cls.task, cls.rows = T.synthetic_task("dev", 4)            # shelf life = long-term months here
        cls.units = T.units_of(cls.task, cls.rows)

    def render(self, k):
        tmp, out, res = run(self.task, MG.MemoryGraph(self.rows), Scripted(self.task, self.rows, choice={kind: k for kind in S.M23B_SHAPES}))
        self.addCleanup(tmp.cleanup)
        self.assertTrue(res["accepted"], res)
        ref = (out / "ref" / "p5_placements.jsonl", out / "ref" / "p8")
        return out / "render_1", ref

    def check(self, folder, ref, tamper=None):
        if tamper:
            pl = [json.loads(x) for x in (folder / "placements.jsonl").read_text(encoding="utf-8").splitlines()]
            tamper(pl)
            (folder / "placements.jsonl").write_text("\n".join(json.dumps(x) for x in pl) + "\n", encoding="utf-8")
        return X.run(folder, self.rows, *ref)

    def swap_ids(self, a, b):
        def tamper(pl):
            ia = next(i for i, p in enumerate(pl) if p["id"] == a)
            ib = next(i for i, p in enumerate(pl) if p["id"] == b)
            pl[ia]["id"], pl[ib]["id"] = pl[ib]["id"], pl[ia]["id"]
        return tamper

    def test_each_wording_passes_untouched_and_fails_with_two_numbers_swapped(self):
        pub = self.task["public"]
        pairs = [(pub["st_low"]["fact_id"], pub["st_high"]["fact_id"]), (pub["ex_low"]["fact_id"], pub["ex_high"]["fact_id"]),
                 (pub["long"]["fact_id"], pub["accel"]["fact_id"]), (pub["shelf"]["fact_id"], pub["st_low"]["fact_id"])]
        g = self.task["results"][0]
        pairs.append((g["stat"]["min"], g["stat"]["max"]))
        for k in range(max(len(v) for v in S.M23B_SHAPES.values())):
            for a, b in pairs:
                folder, ref = self.render(k)
                self.assertTrue(self.check(folder, ref)["passed"], (k, a))
                self.assertFalse(self.check(folder, ref, self.swap_ids(a, b))["passed"], (k, a, b))

    def test_two_equal_values_in_different_places_cannot_be_swapped(self):
        pub = self.task["public"]
        self.assertEqual(self.rows[pub["shelf"]["fact_id"]]["value_text"], self.rows[pub["long"]["fact_id"]]["value_text"])
        for k in range(max(len(v) for v in S.M23B_SHAPES.values())):
            folder, ref = self.render(k)
            res = self.check(folder, ref, self.swap_ids(pub["shelf"]["fact_id"], pub["long"]["fact_id"]))
            self.assertFalse(res["passed"], k)

    def test_the_time_point_number_is_checked_as_its_own_fact(self):
        task, rows = next((t, r) for t, r in (T.synthetic_task("dev", i) for i in range(1, 11)) if any(g["attribute"] == "Dissolution (15 min)" for g in t["results"]))
        tmp, out, res = run(task, MG.MemoryGraph(rows), Scripted(task, rows))
        self.addCleanup(tmp.cleanup)
        folder, ref = out / "render_1", (out / "ref" / "p5_placements.jsonl", out / "ref" / "p8")
        self.assertTrue(X.run(folder, rows, *ref)["passed"])
        html = (folder / "M23.html").read_text(encoding="utf-8")
        self.assertIn(">15</span> min)", html)
        (folder / "M23.html").write_text(html.replace(">15</span> min)", ">30</span> min)", 1), encoding="utf-8")   # the time point says 30, the graph says 15
        self.assertFalse(X.run(folder, rows, *ref)["passed"])

    def test_an_old_plain_dissolution_text_still_passes(self):
        ev = Path(__file__).resolve().parent.parent / "evidence" / "T-068" / "run1"
        rows = json.loads((ev / "graph_snapshot.json").read_text(encoding="utf-8"))
        self.assertTrue(X.run(ev, rows)["passed"])


if __name__ == "__main__":
    unittest.main()
