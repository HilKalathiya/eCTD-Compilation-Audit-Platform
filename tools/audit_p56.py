"""Checks a real-model P.5.6 run: re-reads every accepted paragraph against the stored Lek facts, lists rejects by rule, makes the blind sheet (22 real + 3 planted wrong rows) for Hil.

    python tools/audit_p56.py --run evidence/T-047/run/p56_ollama_gemma4-e4b --out evidence/T-047
    python tools/audit_p56.py --score --run <same folder> --out evidence/T-047      # after Hil filled hil_label in blind.csv
"""
import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from audit_p54 import AuditError, LABELS, bad_sentence, load_run, rule_of  # noqa: E402  (shared logic, not copied)
from ectd_engine.validator.spec import verify_render  # noqa: E402
from ectd_engine.writer.batch_facts import fact_id  # noqa: E402
from ectd_engine.writer.facts import with_unit  # noqa: E402
from ectd_engine.writer.spec_facts import BASIS_TEXT, DECLARED, KIND_TEXT, Q3B, digit_count, narrowed, quote_text  # noqa: E402

BLIND_SEED = 7
N_REAL = 22
PLANTED = ("limit changed", "declared limit given a source", "batch count changed")
SAVED_KEYS = ("limit_kind", "limit", "unit", "basis", "n", "min", "max", "n_outside")
SAVED_Q3B_KEYS = ("mdd", "q3b_quote", "q3b_page", "q3b_version")


def expected_task(task, get_fact, known_batches, j, mdd):
    """The task again, straight from the stored facts and the live justification (not from what the writer saved)."""
    values = []
    for b in task["batches"]:
        f = get_fact(fact_id(b, task["column"]))
        if f is None and b not in known_batches:
            raise AuditError(f"{task['task_id']}: batch {b} is not in the batch registry")
        if f is not None:
            values.append(f.value)
    if not values:
        raise AuditError(f"{task['task_id']}: no batch of this window has a stored value")
    from ectd_engine.stats import basic
    lo, hi = (None, j.limit) if j.limit_kind == "NMT" else (j.limit, None)
    exp = dict(task, limit_kind=j.limit_kind, limit=str(j.limit), unit=j.unit, basis=j.basis, n=len(values),
               min=str(min(values)), max=str(max(values)), n_outside=sum(1 for v in values if not basic.conforms(v, lo, hi)))
    if j.basis == Q3B:
        exp.update(mdd=str(mdd), q3b_quote=j.quote, q3b_page=str(j.page), q3b_version=j.doc_version)
    return narrowed(exp)  # the finished text shows only the dose row, so the re-read must expect only that row


def reread(task, result, exp):
    """Problems found when the finished text of an accepted paragraph is compared with the stored facts (empty = right)."""
    keys = SAVED_KEYS + (SAVED_Q3B_KEYS if exp["basis"] == Q3B else ())
    problems = [f"the task saved with the run has {k} = {task.get(k)!r}, the stored facts say {exp[k]!r}"
                for k in keys if task.get(k) != exp[k]]
    return problems + verify_render(result["rendered"], exp)


def audit(tasks, results, expect):
    """Return the audit rows and the summary numbers. expect(task) -> the task rebuilt from the stored facts."""
    rows, rules, examples, all_rules, all_examples = [], Counter(), {}, Counter(), {}
    for r in results:
        task = tasks[r["task_id"]]
        drafts = r["drafts"]
        for d in drafts:
            for p in d["problems"]:
                all_rules[rule_of(p)] += 1
                all_examples.setdefault(rule_of(p), []).append((r["task_id"], bad_sentence(d["text"], p)))
        row = {"task_id": r["task_id"], "attribute": task["attribute"], "n_excluded": r["flags"]["n_excluded"],
               "accepted": r["accepted"], "drafts": len(drafts), "reread": "", "final_rules": "",
               "all_rules": " | ".join(sorted({rule_of(p) for d in drafts for p in d["problems"]}))}
        if r["accepted"]:
            row["reread"] = "right" if not reread(task, r, expect(task)) else "wrong"
        else:
            last = drafts[-1]
            row["final_rules"] = " | ".join(sorted({rule_of(p) for p in last["problems"]}))
            for p in last["problems"]:
                rules[rule_of(p)] += 1
                examples.setdefault(rule_of(p), []).append((r["task_id"], bad_sentence(last["text"], p)))
        rows.append(row)
    acc = [x for x in rows if x["accepted"]]
    summary = {"total": len(rows), "accepted": len(acc), "rejected": len(rows) - len(acc),
               "wrong": sum(1 for x in acc if x["reread"] == "wrong"),
               "drafts_accepted": sum(x["drafts"] for x in acc), "drafts_all": sum(x["drafts"] for x in rows),
               "with_excluded": sum(1 for x in rows if x["n_excluded"]),
               "final_rules": rules, "examples": examples, "all_rules": all_rules, "all_examples": all_examples,
               "first_try": sum(1 for x in acc if x["drafts"] == 1)}
    return rows, summary


def plant(kind, text, exp):
    """A wrong copy of an accepted paragraph, made by code. It must be caught by the re-read, or the plant is useless (error)."""
    unit = "%" if exp["unit"].startswith("%") else " " + exp["unit"]
    word = KIND_TEXT[exp["limit_kind"]]
    if kind == PLANTED[0]:
        bad = text.replace(f"{word} {exp['limit']}{unit}", f"{word} {Decimal(exp['limit']) + Decimal('0.1')}{unit}", 1)
    elif kind == PLANTED[1]:
        bad = text.replace(BASIS_TEXT[DECLARED], "the ICH Q3B(R2) qualification threshold", 1)
    else:
        # counts are written as digits since T-050 ("9 batches"); "\b" so "1 batch" is not found inside "11 batches"
        bad = re.sub(rf"\b{re.escape(digit_count(exp['n']))}\b", digit_count(exp["n"] + 1), text, count=1)
    if bad == text or not verify_render(bad, exp):
        raise AuditError(f"{exp['task_id']}: the planted error '{kind}' was not made or is not caught by the re-read")
    return bad


def pick_blind(results, expects, seed=BLIND_SEED, n_real=N_REAL):
    """22 random accepted paragraphs + 3 planted wrong ones, shuffled. Returns a list of dicts."""
    rng = random.Random(seed)
    acc = sorted((r for r in results if r["accepted"]), key=lambda r: r["task_id"])
    declared = [r for r in acc if expects[r["task_id"]]["basis"] == DECLARED]
    if not declared:
        raise AuditError("no accepted declared-basis paragraph to plant 'declared limit given a source' in")
    if len(acc) < n_real + len(PLANTED):
        raise AuditError(f"only {len(acc)} accepted paragraphs; the blind sheet needs {n_real + len(PLANTED)}")
    used, items = set(), []
    for kind in (PLANTED[1], PLANTED[0], PLANTED[2]):
        pool = [r for r in (declared if kind == PLANTED[1] else acc) if r["task_id"] not in used]
        r = rng.choice(pool)
        used.add(r["task_id"])
        items.append({"task_id": r["task_id"], "text": plant(kind, r["rendered"], expects[r["task_id"]]), "planted": kind})
    for r in rng.sample([r for r in acc if r["task_id"] not in used], n_real):
        items.append({"task_id": r["task_id"], "text": r["rendered"], "planted": ""})
    rng.shuffle(items)
    return items


def facts_text(exp):
    """The true facts of the window, in words, for Hil to compare with the paragraph."""
    t = (f"limit = {KIND_TEXT[exp['limit_kind']]} {with_unit(exp['limit'], exp['unit'])}; basis = {BASIS_TEXT[exp['basis']]}; "
         f"batches with a result = {exp['n']}; lowest = {with_unit(exp['min'], exp['unit'])}; "
         f"highest = {with_unit(exp['max'], exp['unit'])}; batches outside the limit = {exp['n_outside']}")
    if exp["basis"] == Q3B:
        t += f"; assumed maximum daily dose = {exp['mdd']} mg; Q3B quote = {quote_text(exp)}"
    return t


def write_outputs(out_dir, rows, summary, results, tasks, expect):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["task_id", "attribute", "n_excluded", "accepted", "drafts", "reread", "final_rules", "all_rules"]
    with open(out / "audit.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    expects = {r["task_id"]: expect(tasks[r["task_id"]]) for r in results if r["accepted"]}
    picked = pick_blind(results, expects)
    with open(out / "blind.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["blind_id", "attribute", "facts", "text", "hil_label"])
        for i, p in enumerate(picked, start=1):
            w.writerow([f"B{i:02d}", tasks[p["task_id"]]["attribute"], facts_text(expects[p["task_id"]]), p["text"], ""])
    with open(out / "blind_key.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["blind_id", "task_id", "planted"])
        for i, p in enumerate(picked, start=1):
            w.writerow([f"B{i:02d}", p["task_id"], p["planted"]])
    s = summary
    L = ["# T-047 audit summary: P.5.6 justification writer with the real model", "",
         f"- windows: {s['total']} ({s['with_excluded']} with a quarantined batch)",
         f"- accepted: {s['accepted']} / {s['total']}; rejected: {s['rejected']}",
         f"- accepted on the first draft: {s['first_try']}",
         f"- drafts per accepted paragraph: {s['drafts_accepted']} drafts / {s['accepted']} paragraphs",
         f"- drafts per window (all): {s['drafts_all']} / {s['total']}",
         f"- independent re-read of accepted paragraphs: wrong = {s['wrong']}", "",
         "## Rejected final drafts, by rule (a draft can break several rules)"]
    if not s["final_rules"]:
        L.append("- none")
    for rule, n in s["final_rules"].most_common():
        L.append(f"- {n}x {rule}")
        for tid, sent in s["examples"][rule][:3]:
            L.append(f"    - {tid}: \"{sent}\"")
    L += ["", "## Every rule that fired on any draft (including drafts later fixed)"]
    for rule, n in s["all_rules"].most_common():
        L.append(f"- {n}x {rule}")
        for tid, sent in s["all_examples"][rule][:3]:
            L.append(f"    - {tid}: \"{sent}\"")
    L += ["", f"Blind sheet: {len(picked)} rows in blind.csv ({len(PLANTED)} planted wrong rows hidden among them); "
              "Hil fills hil_label with right or wrong."]
    (out / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return "\n".join(L)


def score(out_dir, rows):
    """PASS only if Hil marked every planted row wrong AND agrees with the re-read on the others.

    Missing or odd labels stop with an error; they are never counted as right."""
    out = Path(out_dir)
    if not (out / "blind.csv").is_file() or not (out / "blind_key.csv").is_file():
        raise AuditError(f"{out}: blind.csv or blind_key.csv is missing; run the audit first")
    with open(out / "blind.csv", newline="", encoding="utf-8") as f:
        sheet = list(csv.DictReader(f))
    with open(out / "blind_key.csv", newline="", encoding="utf-8") as f:
        key = {r["blind_id"]: r for r in csv.DictReader(f)}
    if not sheet:
        raise AuditError("blind.csv has no rows")
    unlabelled = [r["blind_id"] for r in sheet if (r.get("hil_label") or "").strip().lower() not in LABELS]
    if unlabelled:
        raise AuditError(f"hil_label is empty or not 'right'/'wrong' for {len(unlabelled)} row(s): {', '.join(unlabelled)}")
    reread_of = {x["task_id"]: x["reread"] for x in rows}
    missed, differ, hil_wrong, n_planted = [], [], [], 0
    for r in sheet:
        label = r["hil_label"].strip().lower()
        k = key[r["blind_id"]]
        if label == "wrong":
            hil_wrong.append(r["blind_id"])
        if k["planted"]:
            n_planted += 1
            if label != "wrong":
                missed.append((r["blind_id"], k["planted"]))
        elif label != reread_of.get(k["task_id"]):
            differ.append((r["blind_id"], k["task_id"], label, reread_of.get(k["task_id"])))
    return {"n": len(sheet), "planted": n_planted, "missed": missed, "hil_wrong": hil_wrong, "differ": differ,
            "pass": n_planted == len(PLANTED) and not missed and not differ}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="folder made by writer_run.py --kind p56 --audit")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "T-047"))
    ap.add_argument("--score", action="store_true", help="compare Hil's blind labels with the planted rows and the re-read")
    args = ap.parse_args(argv)
    try:
        from ectd_engine.specs import load, p56
        from ectd_engine.writer.batch_facts import LoaderStore
        store = LoaderStore()
        spec = load.load()
        live = {r.attribute: j for r, j in zip(spec.rows, p56.compute(spec, store))}
        tasks, results = load_run(args.run)

        def expect(task):
            return expected_task(task, store.get, store.known_batches, live[task["column"]], spec.mdd.value)
        rows, summary = audit(tasks, results, expect)
        if args.score:
            sc = score(args.out, rows)
            print(f"Hil labelled {sc['n']} rows: planted rows = {sc['planted']}, missed = {len(sc['missed'])} {sc['missed']}; "
                  f"differs from the re-read on the other rows = {len(sc['differ'])}")
            for d in sc["differ"]:
                print(f"  {d[0]} ({d[1]}): Hil says {d[2]}, re-read says {d[3]}")
            print("SCORE: PASS" if sc["pass"] else "SCORE: FAIL (Hil's labels do not count)")
            return 0 if sc["pass"] else 1
        print(write_outputs(args.out, rows, summary, results, tasks, expect))
        return 0 if summary["wrong"] == 0 else 1
    except AuditError as e:
        print(f"AUDIT ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
