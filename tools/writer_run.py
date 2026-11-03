"""Run the engine writer on the 8 test sections with a chosen model and print how many were accepted.

    python tools/writer_run.py --backend mock
    python tools/writer_run.py --backend ollama --model gemma4:e4b
    python tools/writer_run.py --backend openai --model <name> --base-url http://localhost:8080/v1
    python tools/writer_run.py --kind p54 --backend mock --out <folder>     # 3.2.P.5.4 batch analyses on Lek facts
    python tools/writer_run.py --kind p54 --audit 130 --backend ollama --out <folder>   # N real Lek windows (T-042)
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


def make_client(args):
    if args.backend == "mock":
        return BatchMockClient() if args.kind == "p54" else MockClient()
    if args.backend == "openai":
        return OpenAIClient(args.model, args.base_url or "http://localhost:8080/v1", args.num_predict)
    return OllamaClient(args.model, args.base_url or "http://localhost:11434", args.num_ctx, args.num_predict,
                        think=args.think == "on")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=["p83", "p54"], default="p83",
                    help="p83 = stability paragraphs (default); p54 = batch analyses on Lek facts")
    ap.add_argument("--backend", choices=["ollama", "openai", "mock"], default="ollama")
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--max-drafts", type=int, default=MAX_DRAFTS)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--num-predict", type=int, default=600)
    ap.add_argument("--think", choices=["off", "on"], default="off")
    ap.add_argument("--tasks", default=None, help="comma-separated task ids (default: all)")
    ap.add_argument("--audit", type=int, default=0, metavar="N",
                    help="p54 only: use N fixed-seed windows of real Lek batches instead of the 6 task file entries")
    ap.add_argument("--seed", type=int, default=AUDIT_SEED, help="seed for --audit windows")
    ap.add_argument("--data", default=None, help="tasks file (default depends on --kind)")
    ap.add_argument("--out", default=str(ROOT / "outputs" / "writer_run"),
                    help="folder for accepted sections and drafts.jsonl")
    args = ap.parse_args(argv)

    data = args.data or str(ROOT / "data" / "tasks" / "p54_tasks.json" if args.kind == "p54"
                            else ROOT / "writer_test" / "data" / "tasks.json")
    if args.audit and args.kind != "p54":
        ap.error("--audit works only with --kind p54")
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
