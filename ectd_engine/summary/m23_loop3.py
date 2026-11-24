"""The T-073 writing loop for Module 2.3: like m23_loop2, plus claim gates that read the graph (one limit source, "demonstrated" only for clean data, no extrapolation against the data).

Gates (all must pass; default = reject):
 (a) no digit, number word or degree sign in the draft   (b) the slots are the unit's own and in their own places
 (c) every rendered sentence full-matches one wording of the closed set (review/shapes.py M23C_SHAPES, in the expected kind order)
 (d) summary/crosscheck.py on the saved HTML and Word file: every number MATCH, nothing unplaced
 (e) every word of the rendered text is in the closed vocabulary
 (f) "no result outside the limit" / "within the specification limits" only when the outside-limit count of that group is 0, "had results outside
     the limit" only when it is above 0; the count is worked out at gate time from the graph rows, against the ONE limit source (m23_rules)
 (g) a "demonstrated" wording (needs "clean") only when every long-term and intermediate result of the graph is inside its limit
 (h) a shelf life beyond the long-term data only when m23_rules.extrapolation_blockers(rows) is empty
Claim sentences are saved with <span class="claim" data-src="fact ids"> (the derived facts they depend on); m23_compare3 checks those links.
"""
import json
import re
from decimal import Decimal
from pathlib import Path

from ectd_engine.render import html as H
from ectd_engine.render.numbers import NUMBER
from ectd_engine.review import shapes as S
from ectd_engine.summary import build as B
from ectd_engine.summary import crosscheck as X
from ectd_engine.summary import m23_rules as R
from ectd_engine.summary import m23_tasks3 as T3
from ectd_engine.summary.m23_loop import DEGREE_SIGNS, MAX_DRAFTS, PH, SEED, _clean, split_draft


def gate_unit(unit, text, rows):
    """(problems, rendered sentences). problems == [] means gates a, b, c, e, f, g and h passed (gate d runs on the whole document)."""
    text = text or ""
    if not text.strip():
        return ["(a) empty output"], None
    problems = []
    bare = PH.sub("", text)
    if re.search(r"\d", bare):
        problems.append("(a) the draft writes a digit; use a [[placeholder]] for every value")
    for m in NUMBER.finditer(bare):
        if not re.search(r"\d", m.group(0)):
            problems.append(f"(a) the draft writes a number word ({m.group(0)!r}); use a [[placeholder]]")
    if any(c in bare for c in DEGREE_SIGNS):
        problems.append("(a) the draft writes a degree sign; the placeholder already holds it")
    used = PH.findall(text)
    for name in dict.fromkeys(used):
        if name not in unit["slots"]:
            problems.append(f"(b) [[{name}]] is not in the FACTS list")
    for name in unit["required"]:
        if name not in used:
            problems.append(f"(b) missing placeholder [[{name}]]")
    left = PH.sub("", text)
    if "[[" in left or "]]" in left or "{{" in left or "}}" in left:
        problems.append("(b) a placeholder is not written exactly as [[name]]")
    if problems:
        return problems, None
    slots, expect = unit["slots"], unit["expect"]
    sentences = split_draft(unit, text)
    rendered = [PH.sub(lambda m: slots[m.group(1)]["text"], s) for s in sentences]
    if len(sentences) != len(expect):
        problems.append(f"(c) the unit needs exactly {len(expect)} sentence(s) in the order of the instructions; the draft has {len(sentences)}")
    outside = R.outside_count(rows, unit["condition"], unit["attribute"]) if unit["kind"] == "result" else None
    study_blockers = R.study_blockers(rows) if unit["kind"] == "public" else []
    for i, (tmpl, done) in enumerate(zip(sentences, rendered)):
        got = S.m23c_classify(done, unit["names"])
        if got is None:
            problems.append(f"(c) sentence {i + 1}: unrecognised: it fits none of the allowed sentence wordings")
            continue
        kind, shape, needs, shape_slots = got
        if i >= len(expect):
            continue
        if kind != expect[i]:
            problems.append(f"(c) sentence {i + 1}: this is a {kind} sentence but a {expect[i]} sentence belongs here")
            continue
        want = [unit["rows"][i - 1][2]] if kind == "spec_row" else S.m23b_slots(shape_slots, unit.get("has_tp"))
        if PH.findall(tmpl) != want:
            problems.append(f"(b) sentence {i + 1}: holds {', '.join('[[' + s + ']]' for s in PH.findall(tmpl))} but this place takes "
                            f"{', '.join('[[' + s + ']]' for s in want)}; each value belongs to its own place")
        if kind == "spec_row":
            test, lim_kind, _ = unit["rows"][i - 1]
            if not done.startswith((f"{test}: {lim_kind} ", f"{test} {lim_kind} ")):
                problems.append(f"(c) sentence {i + 1}: the test name and limit kind must match the placeholder's own test")
        if needs == "zero" and outside != 0:
            problems.append(f"(f) sentence {i + 1} says no result is outside the limit, but the graph counts results outside the limit for this condition and attribute")
        if needs == "some" and outside == 0:
            problems.append(f"(f) sentence {i + 1} says results are outside the limit, but the graph counts none for this condition and attribute")
        if needs == "clean" and study_blockers:
            problems.append(f"(g) sentence {i + 1} says stability was demonstrated, but the graph holds {study_blockers[0]}; write a neutral sentence "
                            "(for example that data are available) without the word demonstrated")
    if unit["kind"] == "public":
        shelf, long_ = (Decimal(rows[unit["slots"][k]["fact_id"]]["value_text"]) for k in ("shelf", "long"))
        if shelf > long_ and R.extrapolation_blockers(rows):
            problems.append("(h) the proposed shelf life is longer than the long-term data, but the graph does not allow that extrapolation: "
                            + R.extrapolation_blockers(rows)[0])
    unknown = S.m23_unknown_words(" ".join(rendered), S.m23c_vocabulary(unit["words"]))
    if unknown:
        problems.append("(e) words that are not allowed here: " + ", ".join(unknown))
        names = [n for n in unit["words"] if isinstance(n, str)]
        for w in unknown:
            home = next((n for n in names if w.lower() in n.lower().split()), None)
            if home:                                                       # DEV tuning (T-073): say what the fix is when the word is a name written in the wrong case
                problems.append(f"(e) '{w}' belongs to the name '{home}': write that whole name exactly as given, with its capital letters")
    return problems, (None if problems else rendered)


# ---- the document ------------------------------------------------------------------------------------------------------------------

def _row(slot):
    return {"fact_id": slot["fact_id"], "value_text": slot["value"], "unit": slot["unit"]}


def build_sections(task, rows, units, states):
    """{part: [Section | Rejected]} from the accepted drafts; every number is written here from the graph rows; claim sentences carry their fact ids."""
    out = {"2.3.P.5": [], "2.3.P.8": []}

    def fill(sentence, u):
        return PH.sub(lambda m: B._with_unit(_row(u["slots"][m.group(1)])), sentence)
    for u in units:
        draft, part = states[u["unit_id"]]["accepted"], u["part"]
        try:
            sentences = split_draft(u, draft)
            if u["kind"] == "spec":
                out[part].append(H.finish(part, "spec_intro", "spec_intro", [H.make_paragraph("spec_intro", sentences[0], {})]))
                paras = []
                for s in task["spec"]:
                    r = rows[s["fact_id"]]
                    marked = f"{r['test']}\t{r['limit_kind']} {B._with_unit(r)}"
                    paras.append(H.make_paragraph(f"row:{s['attribute']}", marked, {s["fact_id"]: "specification limit"}, table_row=True))
                out[part].append(H.finish(part, "spec_table", "spec_table", paras))
            elif u["kind"] == "public":
                labels = {s["fact_id"]: k for k, s in u["slots"].items()}
                done = [fill(s, u) for s in sentences]
                para = H.make_paragraph("public", " ".join(done), labels)
                pos, claims = 0, []
                for sent in (PH.sub(lambda m: u["slots"][m.group(1)]["text"], s) for s in sentences):      # the text as saved, without the id marks
                    kind = (S.m23c_classify(sent, {}, kinds=("shelf", "excursion", "study")) or ("",))[0]
                    if kind == "study":
                        claims.append((pos, pos + len(sent), u["study_ids"]))
                    elif kind == "shelf" and u["extrapolates"]:
                        claims.append((pos, pos + len(sent), u["shelf_ids"]))
                    pos += len(sent) + 1
                para.claims = claims
                out[part].append(H.finish(part, "public", "public", [para]))
            else:
                labels = {s["fact_id"]: k for k, s in u["slots"].items()}
                paras = [H.make_paragraph("results", fill(s, u), labels) for s in sentences]
                paras[1].claims = [(0, len(paras[1].text), u["claim_ids"])]
                out[part].append(H.finish(part, f"{u['condition']}|{u['attribute']}", "results", paras))
        except B.Refused as e:
            out[part].append(H.Rejected(part, u["unit_id"], u["kind"], str(e), [str(e)]))
    return out


# ---- asking and retrying -----------------------------------------------------------------------------------------------------------

def _attempt(client, unit, st, task_id, rows, log, build_messages, seed, temperature):
    view, n = T3.view_of(unit), st["drafts"]
    messages = build_messages(view, st["feedback"])
    reply = client.chat(messages, temperature, seed + n, context={"task_id": task_id, "unit_id": unit["unit_id"], "unit": view})
    text = reply["text"]
    problems, rendered = gate_unit(unit, text, rows)
    st["drafts"] += 1
    log({"task_id": task_id, "unit_id": unit["unit_id"], "draft": n + 1, "seed": seed + n, "temperature": temperature, "messages": messages,
         "text": text, "passed": not problems, "problems": problems, "seconds": reply.get("seconds", 0),
         "output_tokens": reply.get("output_tokens", 0), **({"planted": True} if reply.get("planted") else {})})
    if problems:
        st["feedback"].append((_clean(text or "(empty)"), [_clean(p) for p in problems]))
        st["accepted"] = None
        return False
    st["accepted"], st["rendered"] = text, rendered
    return True


def _fill(client, unit, st, task_id, rows, log, build_messages, seed, temperature, max_drafts):
    while st["accepted"] is None and st["drafts"] < max_drafts:
        _attempt(client, unit, st, task_id, rows, log, build_messages, seed, temperature)


def run_world(client, task, out_dir, graph, check_rows=None, ref=None, max_drafts=MAX_DRAFTS, seed=SEED, temperature=0.0, build_messages=None):
    """Write one whole 2.3 for a task (see m23_loop2.run_world; same files). The task must pass consistency_problems3 or no draft is asked."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder (runs are never overwritten)")
    out.mkdir(parents=True)
    if build_messages is None:
        from ectd_engine.summary import m23_prompt3
        build_messages = m23_prompt3.build_messages
    rows = graph.rows()
    check_rows = rows if check_rows is None else check_rows
    (out / "graph_snapshot.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (out / "graph_snapshot_check.json").write_text(json.dumps(check_rows, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    result = {"task_id": task["task_id"], "set": task["set"], "synthetic": task["synthetic"], "graph": graph.namespace, "accepted": False,
              "reason": "", "render": "", "renders": 0, "drafts": {}}
    problems = T3.consistency_problems3(task, rows)
    if problems:
        result["reason"] = "task is not self-consistent (no draft was asked): " + "; ".join(problems)
    elif rows != check_rows:
        result["reason"] = "the graph read for rendering and the graph read for the cross-check are not the same"
    if result["reason"]:
        (out / "result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return result
    if ref is None:
        ref = T3.write_reference3(task, rows, out / "ref") if task["synthetic"] else (X.P5_PLACEMENTS, X.P8_SECTIONS)
    units = T3.units_of3(task, rows)
    states = {u["unit_id"]: {"drafts": 0, "feedback": [], "accepted": None, "rendered": None} for u in units}
    with open(out / "attempts.jsonl", "w", encoding="utf-8") as fh:
        def log(rec):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
        for u in units:
            _fill(client, u, states[u["unit_id"]], task["task_id"], rows, log, build_messages, seed, temperature, max_drafts)
        while True:
            bad = [u["unit_id"] for u in units if states[u["unit_id"]]["accepted"] is None]
            if bad:
                result["reason"] = "units rejected: " + ", ".join(bad)
                break
            result["renders"] += 1
            folder = out / f"render_{result['renders']}"
            report = B.write_run(folder, None, sections=build_sections(task, rows, units, states), title=task["title"])
            cc = X.run(folder, check_rows, ref[0], ref[1])
            X.write_outputs(cc, folder)
            unplaced = [r for r in cc["rows"] if r["fact_id"].startswith("unplaced:")]
            ok = cc["passed"] and not unplaced and not report["rejected"] and not report["docx_problems"] and report["uncovered"] == 0
            log({"task_id": task["task_id"], "gate": "d", "render": folder.name, "passed": ok, "counts": cc["counts"], "unplaced": len(unplaced),
                 "problems": cc["problems"] + report["docx_problems"] + [f"{a}: {b}" for a, b in report["rejected"]]})
            if ok:
                result.update(accepted=True, render=folder.name, counts=cc["counts"])
                break
            failing = {r["fact_id"] for r in cc["rows"] if r["verdict"] == "FAIL"}
            hit = [u for u in units if failing & {s["fact_id"] for s in u["slots"].values()}] or list(units)
            retry = [u for u in hit if states[u["unit_id"]]["drafts"] < max_drafts]
            if not retry:
                result["reason"] = "(d) the cross-check failed and no draft is left to retry"
                result["counts"] = cc["counts"]
                break
            why = sorted({_clean(r["reason"]) for r in cc["rows"] if r["verdict"] == "FAIL" and r["reason"]})[:4] or ["the cross-check failed"]
            for u in retry:
                st = states[u["unit_id"]]
                st["feedback"].append((_clean(st["accepted"]), ["(d) the cross-check of the finished document failed: " + "; ".join(why)]))
                st["accepted"] = None
                _fill(client, u, st, task["task_id"], rows, log, build_messages, seed, temperature, max_drafts)
    result["drafts"] = {k: v["drafts"] for k, v in states.items()}
    (out / "result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return result
