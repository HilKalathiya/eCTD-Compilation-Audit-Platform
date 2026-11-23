"""The 2.3 writing loop: Gemma writes [[slot]] text for each unit, code gates it (a-e), renders the numbers, and the cross-check has the last word.

Gates, all of them must pass (default = reject):
 (a) the draft holds no digit, no number word, no degree sign (the slots removed first; no exemption list is used here)
 (b) every slot used is in the task, every required slot is used once, and each sentence holds the slots of its own place
 (c) every rendered sentence full-matches one 2.3 sentence form (review/shapes.py M23_TEMPLATES), in the expected order
 (d) summary/crosscheck.py on the saved rendered HTML and Word file: every number MATCH, nothing unplaced
 (e) every word of the rendered text is in the closed vocabulary made from the sentence forms and the task's own words
A rejected draft is sent back with the problems (digits replaced by #) up to MAX_DRAFTS drafts per unit; every draft is logged.
"""
import json
import re
from collections import Counter
from pathlib import Path

from ectd_engine.render import html as H
from ectd_engine.render.numbers import NUMBER
from ectd_engine.review import shapes as S
from ectd_engine.summary import build as B
from ectd_engine.summary import crosscheck as X
from ectd_engine.summary import m23_tasks as T
from ectd_engine.validator.stability import split_sentences

MAX_DRAFTS = 4
SEED = 42
PH = re.compile(r"\[\[([a-z_]+)\]\]")
DEGREE_SIGNS = "°º˚"


def _clean(text):
    """Text that is safe to send back to the model: every digit becomes #, so no number can travel back."""
    return re.sub(r"\d", "#", text)


def split_draft(unit, text):
    """Sentences of a draft: one per line for the specification unit, else split after each full stop."""
    if unit["kind"] == "spec":
        return [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return split_sentences(text)


def gate_unit(unit, text):
    """(problems, rendered sentences). problems == [] means gates a, b, c and e all passed (gate d runs on the whole document)."""
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
    for name, n in Counter(used).items():
        if n > 1 and name in unit["slots"]:
            problems.append(f"(b) [[{name}]] is used {'twice' if n == 2 else 'more than once'}; use it once")
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
        problems.append(f"(c) the unit needs exactly {len(expect)} sentence(s) in the example order; the draft has {len(sentences)}")
    for i, (tmpl, done) in enumerate(zip(sentences, rendered)):
        got = S.m23_classify(done, unit["names"])
        if got is None:
            problems.append(f"(c) sentence {i + 1}: unrecognised: it fits none of the allowed sentence forms; copy the example form exactly")
            continue
        form, groups = got
        if i >= len(expect):
            continue
        want_form, want_slots = expect[i]
        if form != want_form:
            problems.append(f"(c) sentence {i + 1}: this is the {form} form but the {want_form} form belongs here")
        elif PH.findall(tmpl) != want_slots:
            problems.append(f"(b) sentence {i + 1}: holds {', '.join('[[' + s + ']]' for s in PH.findall(tmpl))} but this place takes "
                            f"{', '.join('[[' + s + ']]' for s in want_slots)}; each value belongs to its own place")
        elif unit["kind"] == "spec" and form == "spec_row" and (groups["test1"], groups["kind1"]) != tuple(unit["rows"][i - 1]):
            problems.append(f"(c) sentence {i + 1}: the test name and limit kind must match the placeholder's own test")
    unknown = S.m23_unknown_words(" ".join(rendered), S.m23_vocabulary(unit["words"]))
    if unknown:
        problems.append("(e) words that are not allowed here: " + ", ".join(unknown))
    return problems, (None if problems else rendered)


# ---- the document ------------------------------------------------------------------------------------------------------------------

def _row(slot):
    return {"fact_id": slot["fact_id"], "value_text": slot["value"], "unit": slot["unit"]}


def build_sections(task, units, states):
    """{part: [Section | Rejected]} from the accepted drafts. Numbers are written here from the task's facts; the draft only chose the words."""
    out = {"2.3.P.5": [], "2.3.P.8": []}
    for u in units:
        draft, part = states[u["unit_id"]]["accepted"], u["part"]
        try:
            if u["kind"] == "spec":
                lines = split_draft(u, draft)
                out[part].append(H.finish(part, "spec_intro", "spec_intro", [H.make_paragraph("spec_intro", lines[0], {})]))
                paras = []
                for spec in task["spec"]:
                    marked = f"{spec['test']}\t{spec['limit_kind']} {B._with_unit(_row(spec))}"
                    paras.append(H.make_paragraph(f"row:{spec['attribute']}", marked, {spec["fact_id"]: "specification limit"}, table_row=True))
                out[part].append(H.finish(part, "spec_table", "spec_table", paras))
                continue
            sentences = split_draft(u, draft)
            marked = " ".join(PH.sub(lambda m: B._with_unit(_row(u["slots"][m.group(1)])), s) for s in sentences)
            if u["kind"] == "public":
                labels = {s["fact_id"]: k for k, s in u["slots"].items()}
                out[part].append(H.finish(part, "public", "public", [H.make_paragraph("public", marked, labels)]))
            else:
                labels = {u["slots"]["low"]["fact_id"]: "lowest stored result", u["slots"]["high"]["fact_id"]: "highest stored result"}
                out[part].append(H.finish(part, f"{u['condition']}|{u['attribute']}", "results", [H.make_paragraph("results", marked, labels)]))
        except B.Refused as e:
            out[part].append(H.Rejected(part, u["unit_id"], u["kind"], str(e), [str(e)]))
    return out


# ---- asking and retrying -----------------------------------------------------------------------------------------------------------

def _attempt(client, unit, st, task_id, log, build_messages, seed, temperature):
    """One draft: ask, gate, log. Returns True if it passed gates a, b, c and e."""
    view, n = T.view_of(unit), st["drafts"]
    messages = build_messages(view, st["feedback"])
    reply = client.chat(messages, temperature, seed + n, context={"task_id": task_id, "unit_id": unit["unit_id"], "unit": view})
    text = reply["text"]
    problems, rendered = gate_unit(unit, text)
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


def _fill(client, unit, st, task_id, log, build_messages, seed, temperature, max_drafts):
    while st["accepted"] is None and st["drafts"] < max_drafts:
        _attempt(client, unit, st, task_id, log, build_messages, seed, temperature)


def run_world(client, task, out_dir, rows=None, ref=None, max_drafts=MAX_DRAFTS, seed=SEED, temperature=0.0, build_messages=None):
    """Write one whole 2.3 for a task. Folder out_dir must be new. Files: attempts.jsonl (every draft with its messages), render_<k>/ (HTML, Word,
    placements, crosscheck.csv, summary.md, report.txt for every render), ref/ (synthetic tasks), result.json. Returns the result dict."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f"{out} already exists; use a new folder (runs are never overwritten)")
    out.mkdir(parents=True)
    if build_messages is None:
        from ectd_engine.summary import m23_prompt
        build_messages = m23_prompt.build_messages
    rows = task["graph_rows"] if rows is None else rows
    if ref is None:
        ref = T.write_reference(task, out / "ref") if task["synthetic"] else (X.P5_PLACEMENTS, X.P8_SECTIONS)
    units = T.units_of(task)
    states = {u["unit_id"]: {"drafts": 0, "feedback": [], "accepted": None, "rendered": None} for u in units}
    result = {"task_id": task["task_id"], "set": task["set"], "synthetic": task["synthetic"], "accepted": False, "reason": "", "render": "", "renders": 0}
    with open(out / "attempts.jsonl", "w", encoding="utf-8") as fh:
        def log(rec):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
        for u in units:
            _fill(client, u, states[u["unit_id"]], task["task_id"], log, build_messages, seed, temperature, max_drafts)
        while True:
            bad = [u["unit_id"] for u in units if states[u["unit_id"]]["accepted"] is None]
            if bad:
                result["reason"] = "units rejected: " + ", ".join(bad)
                break
            result["renders"] += 1
            folder = out / f"render_{result['renders']}"
            report = B.write_run(folder, None, sections=build_sections(task, units, states), title=task["title"])
            cc = X.run(folder, rows, ref[0], ref[1])
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
                _fill(client, u, st, task["task_id"], log, build_messages, seed, temperature, max_drafts)
    result["drafts"] = {k: v["drafts"] for k, v in states.items()}
    (out / "result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return result
