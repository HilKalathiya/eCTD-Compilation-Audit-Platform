"""Run the engine writer on the 8 test sections with a chosen model and print how many were accepted.

    python tools/writer_run.py --backend mock
    python tools/writer_run.py --backend ollama --model gemma4:e4b
    python tools/writer_run.py --backend openai --model <name> --base-url http://localhost:8080/v1
    python tools/writer_run.py --kind p54 --backend mock --out <folder>     # 3.2.P.5.4 batch analyses on Lek facts
    python tools/writer_run.py --kind p54 --audit 130 --backend ollama --out <folder>   # N real Lek windows (T-042)
    python tools/writer_run.py --kind p56 --backend mock --out <folder>     # 3.2.P.5.6 justification per spec attribute (T-046)
    python tools/writer_run.py --kind p56 --audit 130 --backend ollama --out <folder>   # N real Lek subsets (T-047)
    python tools/writer_run.py --kind p83 --backend mock --out <folder>     # 3.2.P.8.3 stability: public paragraph + one per condition x attribute (T-064)
    python tools/writer_run.py --kind p83 --heldout --data evidence/T-065/heldout.csv --backend mock --out <new folder>   # 20 held-out tasks (T-065)
    (the old 8-section stability test of writer_test is --kind p83_8task, still the default; a --out folder that already holds a p83 run is refused)
"""
AUDIT_SEED = 42
WINDOW = 12


def make_windows(store, count, seed=AUDIT_SEED, size=WINDOW):
    """Fixed-seed windows of `size` real Lek batches: the 5 attributes in turn; 2 of 3 impurity windows hold 1-3 quarantined batches."""
    rng = random.Random(seed)
    cols = list(lek.COLUMNS)
    out = []
    for i in range(count):
        col = cols[i % len(cols)]
        have = sorted((b for b in store.known_batches if store.get(fact_id(b, col)) is not None
                       and places(store.get(fact_id(b, col)).value) <= 2), key=id_key)
        gone = sorted((b for b in store.known_batches if store.get(fact_id(b, col)) is None), key=id_key)
        k = rng.randint(1, min(3, len(gone))) if (col in lek.PARTS and gone and rng.randrange(3) != 0) else 0
        ids = rng.sample(gone, k) + rng.sample(have, size - k)
        out.append({"task_id": f"w{i:03d}_{col}", "section": "3.2.P.5.4", "product": "Lek tablets",
                    "attribute": lek.COLUMNS[col][0], "column": col, "unit": "%", "decimals": 2,
                    "batches": sorted(ids, key=id_key)})
    return out

def make_p56_windows(get_fact, known, live, mdd, count, seed=AUDIT_SEED, low=8, high=30):
    """Fixed-seed P.5.6 windows: the attributes in turn, each over a random subset of real Lek batches.

    live: {column: Justification} (limit, basis, quote come from it). If some batches have no fact for the column
    (quarantined), 2 of 3 windows hold 1-3 of them; they are left out of n/min/max/outside. Numbers are computed here
    from the stored facts with the same rule as p56 (value rounded to the limit's decimals, then compared)."""
    from ectd_engine.stats import basic
    rng = random.Random(seed)
    cols = list(live)
    out = []
    for i in range(count):
        col = cols[i % len(cols)]
        j = live[col]
        have = sorted((b for b in known if get_fact(fact_id(b, col)) is not None), key=id_key)
        gone = sorted((b for b in known if get_fact(fact_id(b, col)) is None), key=id_key)
        k = rng.randint(1, min(3, len(gone))) if (gone and rng.randrange(3) != 0) else 0
        ids = sorted(rng.sample(gone, k) + rng.sample(have, min(rng.randint(low, high), len(have)) - k), key=id_key)
        values = [get_fact(fact_id(b, col)).value for b in ids if get_fact(fact_id(b, col)) is not None]
        lo, hi = (None, j.limit) if j.limit_kind == "NMT" else (j.limit, None)
        task = {"task_id": f"w{i:03d}_{col}", "section": "3.2.P.5.6", "product": "Lek tablets", "attribute": j.test,
                "column": col, "limit_kind": j.limit_kind, "limit": str(j.limit), "unit": j.unit, "basis": j.basis,
                "n": len(values), "min": str(min(values)), "max": str(max(values)),
                "n_outside": sum(1 for v in values if not basic.conforms(v, lo, hi)),
                "batches": ids, "n_excluded": len(ids) - len(values)}
        if j.basis == "q3b_qualification":
            task.update(mdd=str(mdd), q3b_quote=j.quote, q3b_page=str(j.page), q3b_version=j.doc_version)
        out.append(task)
    return out


def make_synthetic_p56_windows(get_fact, known, live, count, seed=AUDIT_SEED):
    """SYNTHETIC windows with batches outside the limit (the real Lek data has none). Declared-basis attributes only.

    Each is a real window whose limit is moved onto one of its own results, so 1 or more results fall outside. The numbers
    still come from the stored facts; only the limit is made up, and every task is marked "synthetic": true."""
    from ectd_engine.stats import basic
    declared = {c: j for c, j in live.items() if j.basis == "declared"}
    rng = random.Random(seed + 1)
    out = []
    for t in make_p56_windows(get_fact, known, declared, None, count, seed + 1):
        vals = sorted(get_fact(fact_id(b, t["column"])).value for b in t["batches"] if get_fact(fact_id(b, t["column"])) is not None)
        nmt = t["limit_kind"] == "NMT"
        for pos in rng.sample(range(len(vals)), len(vals)):
            lim = vals[pos]
            lo, hi = (None, lim) if nmt else (lim, None)
            n_out = sum(1 for v in vals if not basic.conforms(v, lo, hi))
            if n_out:
                break
        else:
            continue
        t.update(task_id="s" + t["task_id"][1:], limit=str(lim), n_outside=n_out, synthetic=True)
        out.append(t)
    return out


import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ectd_engine.loaders import lek  # noqa: E402
from ectd_engine.writer.batch_facts import LoaderStore, fact_id, id_key, places  # noqa: E402
from ectd_engine.writer.batch_loop import BatchMockClient, run_batch_task, write_batch_section  # noqa: E402
from ectd_engine.writer.llm import MockClient, OllamaClient, OpenAIClient  # noqa: E402
from ectd_engine.writer.loop import MAX_DRAFTS, run_task, write_section  # noqa: E402


def run_p56(args, client):
    """3.2.P.5.6 justification paragraphs for the 5 real Lek attributes; numbers and quotes are re-read live, never trusted from the file."""
    from ectd_engine.specs import load, p56
    from ectd_engine.writer.spec_facts import resolve_quote, task_from_justification
    from ectd_engine.writer.spec_loop import run_spec_task, write_spec_section
    store = LoaderStore()
    spec = load.load()
    live = {str(spec.mdd.value): {r.attribute: j for r, j in zip(spec.rows, p56.compute(spec, store))}}
    out = Path(args.out) / f"p56_{args.backend}_{args.model}".replace(":", "-").replace("/", "-")
    (out / "sections").mkdir(parents=True, exist_ok=True)
    if args.audit:  # N subsets of real batches; their numbers are computed here, so the live-file check does not apply
        tasks = make_p56_windows(store.get, store.known_batches, live[str(spec.mdd.value)], spec.mdd.value, args.audit, args.seed)
        (out / "tasks.json").write_text(json.dumps({"seed": args.seed, "tasks": tasks}, indent=1), encoding="utf-8")
    else:
        with open(args.data or str(ROOT / "data" / "tasks" / "p56_tasks.json"), encoding="utf-8") as f:
            tasks = json.load(f)["tasks"]
        if args.tasks:
            wanted = set(args.tasks.split(","))
            tasks = [t for t in tasks if t["task_id"] in wanted]
    def run_set(tasks, folder):
        """Write every task of one set into `folder` (drafts, results, sections); return how many were accepted."""
        accepted = 0
        (folder / "sections").mkdir(parents=True, exist_ok=True)
        with open(folder / "drafts.jsonl", "w", encoding="utf-8") as log, open(folder / "results.jsonl", "w", encoding="utf-8") as results:
            for task in tasks:
                if not args.audit:
                    task = resolve_quote(task, live)
                res = run_spec_task(client, task, max_drafts=args.max_drafts)
                for d in res["drafts"]:
                    log.write(json.dumps({"task_id": task["task_id"], **d}, ensure_ascii=False) + "\n")
                results.write(json.dumps({"task_id": task["task_id"], "accepted": res["accepted"], "rendered": res["rendered"],
                                          "flags": {"n_excluded": task.get("n_excluded", 0)}, "drafts": res["drafts"]},
                                         ensure_ascii=False) + "\n")
                results.flush()
                if res["accepted"]:
                    accepted += 1
                    (folder / "sections" / f"{task['task_id']}.md").write_text(write_spec_section(task, res), encoding="utf-8")
                    print(f"{task['task_id']}: ACCEPTED after {len(res['drafts'])} draft(s)")
                else:
                    print(f"{task['task_id']}: REJECTED after {len(res['drafts'])} draft(s): {'; '.join(res['drafts'][-1]['problems'])}")
        return accepted

    t0 = time.time()
    accepted = run_set(tasks, out)
    print(f"\n{accepted}/{len(tasks)} accepted ({time.time() - t0:.0f} s). Saved in {out}")
    if args.audit and args.synthetic:  # kept in a sub-folder so the real-window audit never mixes them in
        syn = make_synthetic_p56_windows(store.get, store.known_batches, live[str(spec.mdd.value)], args.synthetic, args.seed)
        sdir = out / "synthetic"
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "tasks.json").write_text(json.dumps({"seed": args.seed, "synthetic": True, "tasks": syn}, indent=1), encoding="utf-8")
        s_acc = run_set(syn, sdir)
        print(f"\nSYNTHETIC (n_outside > 0): {s_acc}/{len(syn)} accepted. Saved in {sdir}")
    return 0 if (accepted == len(tasks) or args.audit) else 1


def run_p83(args, client):
    """3.2.P.8.3: one task for the public paragraph and one per condition x attribute; fixed temperature and seed; folder = --out."""
    from ectd_engine.stability.runner import run_p83 as run_all
    meta = {"backend": args.backend, "model": args.model, "think": args.think, "num_ctx": args.num_ctx, "num_predict": args.num_predict}
    meta.update(heldout=args.heldout, data=args.data)
    kw = {"csv_path": args.data} if args.data else {}
    summary = run_all(client, args.out, max_drafts=args.max_drafts, seed=args.seed, temperature=args.temperature,
                      only=args.tasks.split(",") if args.tasks else None, meta=meta, heldout=args.heldout, **kw)
    return 0 if (summary["accepted"] == summary["tasks"] and not summary["wrong_accepted"]) else 1


def make_client(args):
    if args.backend == "mock":
        if args.kind == "p83":
            from ectd_engine.stability.loop import StabilityMockClient
            return StabilityMockClient()
        if args.kind == "p56":
            from ectd_engine.writer.spec_loop import SpecMockClient
            return SpecMockClient()
        return BatchMockClient() if args.kind == "p54" else MockClient()
    if args.backend == "openai":
        return OpenAIClient(args.model, args.base_url or "http://localhost:8080/v1", args.num_predict)
    return OllamaClient(args.model, args.base_url or "http://localhost:11434", args.num_ctx, args.num_predict,
                        think=args.think == "on")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=["p83", "p83_8task", "p54", "p56"], default="p83_8task",
                    help="p83_8task = old 8-section stability test (default); p83 = P.8.3 stability writer (T-064); "
                         "p54 = batch analyses on Lek facts; p56 = spec justification")
    ap.add_argument("--heldout", action="store_true",
                    help="p83 only: the --data file is the synthetic held-out CSV (T-065); outside-limit demo rows are allowed, the public task is left out")
    ap.add_argument("--temperature", type=float, default=0.0, help="p83 only: sampling temperature (default 0)")
    ap.add_argument("--backend", choices=["ollama", "openai", "mock"], default="ollama")
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--max-drafts", type=int, default=MAX_DRAFTS)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--num-predict", type=int, default=600)
    ap.add_argument("--think", choices=["off", "on"], default="off")
    ap.add_argument("--tasks", default=None, help="comma-separated task ids (default: all)")
    ap.add_argument("--audit", type=int, default=0, metavar="N",
                    help="p54/p56: use N fixed-seed windows of real Lek batches instead of the task file entries")
    ap.add_argument("--synthetic", type=int, default=0, metavar="N",
                    help="p56 with --audit: also N SYNTHETIC windows with batches outside the limit (kept in a synthetic/ sub-folder)")
    ap.add_argument("--seed", type=int, default=AUDIT_SEED, help="seed for --audit windows")
    ap.add_argument("--data", default=None, help="tasks file (default depends on --kind)")
    ap.add_argument("--out", default=str(ROOT / "outputs" / "writer_run"),
                    help="folder for accepted sections and drafts.jsonl")
    args = ap.parse_args(argv)

    if args.kind == "p83":
        return run_p83(args, make_client(args))
    if args.kind == "p56":
        return run_p56(args, make_client(args))
    data = args.data or str(ROOT / "data" / "tasks" / "p54_tasks.json" if args.kind == "p54"
                            else ROOT / "writer_test" / "data" / "tasks.json")
    if args.audit and args.kind != "p54":
        ap.error("--audit works only with --kind p54 or p56")
    store = LoaderStore() if args.kind == "p54" else None  # Lek facts as the real loader stores them
    if args.audit:
        tasks = make_windows(store, args.audit, args.seed)
    else:
        with open(data, encoding="utf-8") as f:
            tasks = json.load(f)["tasks"]
    if args.tasks:
        wanted = set(args.tasks.split(","))
        tasks = [t for t in tasks if t["task_id"] in wanted]
    out = Path(args.out) / f"{args.kind + '_' if args.kind == 'p54' else ''}{args.backend}_{args.model}".replace(":", "-").replace("/", "-")
    (out / "sections").mkdir(parents=True, exist_ok=True)
    client = make_client(args)
    if args.audit:
        (out / "tasks.json").write_text(json.dumps({"seed": args.seed, "tasks": tasks}, indent=1), encoding="utf-8")

    accepted, t0 = 0, time.time()
    with open(out / "drafts.jsonl", "w", encoding="utf-8") as log,             open(out / "results.jsonl", "w", encoding="utf-8") as results:
        for task in tasks:
            if store:
                res = run_batch_task(client, task, store.get, store.known_batches, max_drafts=args.max_drafts)
            else:
                res = run_task(client, task, max_drafts=args.max_drafts)
            for d in res["drafts"]:
                log.write(json.dumps({"task_id": task["task_id"], **d}, ensure_ascii=False) + "\n")
            n = len(res["drafts"])
            if store:  # one line per task, written at once so a stopped run keeps what it finished
                results.write(json.dumps({"task_id": task["task_id"], "accepted": res["accepted"], "rendered": res["rendered"],
                                          "table": res["table"], "flags": {"n_excluded": res["flags"]["n_excluded"]},
                                          "drafts": res["drafts"]}, ensure_ascii=False) + "\n")
                results.flush()
            if res["accepted"]:
                accepted += 1
                section = write_batch_section(task, res) if store else write_section(task, res)
                (out / "sections" / f"{task['task_id']}.md").write_text(section, encoding="utf-8")
                print(f"{task['task_id']}: ACCEPTED after {n} draft(s)")
            else:
                print(f"{task['task_id']}: REJECTED after {n} draft(s): {'; '.join(res['drafts'][-1]['problems'])}")
    print(f"\n{accepted}/{len(tasks)} accepted ({time.time() - t0:.0f} s). Saved in {out}")
    return 0 if (accepted == len(tasks) or args.audit) else 1


if __name__ == "__main__":
    sys.exit(main())
