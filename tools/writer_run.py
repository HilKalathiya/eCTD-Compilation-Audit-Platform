"""Run the engine writer on the 8 test sections with a chosen model and print how many were accepted.

    python tools/writer_run.py --backend mock
    python tools/writer_run.py --backend ollama --model gemma4:e4b
    python tools/writer_run.py --backend openai --model <name> --base-url http://localhost:8080/v1
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ectd_engine.writer.llm import MockClient, OllamaClient, OpenAIClient  # noqa: E402
from ectd_engine.writer.loop import MAX_DRAFTS, run_task, write_section  # noqa: E402


def make_client(args):
    if args.backend == "mock":
        return MockClient()
    if args.backend == "openai":
        return OpenAIClient(args.model, args.base_url or "http://localhost:8080/v1", args.num_predict)
    return OllamaClient(args.model, args.base_url or "http://localhost:11434", args.num_ctx, args.num_predict,
                        think=args.think == "on")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["ollama", "openai", "mock"], default="ollama")
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--max-drafts", type=int, default=MAX_DRAFTS)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--num-predict", type=int, default=600)
    ap.add_argument("--think", choices=["off", "on"], default="off")
    ap.add_argument("--tasks", default=None, help="comma-separated task ids (default: all)")
    ap.add_argument("--data", default=str(ROOT / "writer_test" / "data" / "tasks.json"))
    ap.add_argument("--out", default=str(ROOT / "outputs" / "writer_run"),
                    help="folder for accepted sections and drafts.jsonl")
    args = ap.parse_args(argv)

    with open(args.data, encoding="utf-8") as f:
        tasks = json.load(f)["tasks"]
    if args.tasks:
        wanted = set(args.tasks.split(","))
        tasks = [t for t in tasks if t["task_id"] in wanted]
    out = Path(args.out) / f"{args.backend}_{args.model}".replace(":", "-").replace("/", "-")
    (out / "sections").mkdir(parents=True, exist_ok=True)
    client = make_client(args)

    accepted, t0 = 0, time.time()
    with open(out / "drafts.jsonl", "w", encoding="utf-8") as log:
        for task in tasks:
            res = run_task(client, task, max_drafts=args.max_drafts)
            for d in res["drafts"]:
                log.write(json.dumps({"task_id": task["task_id"], **d}, ensure_ascii=False) + "\n")
            n = len(res["drafts"])
            if res["accepted"]:
                accepted += 1
                (out / "sections" / f"{task['task_id']}.md").write_text(write_section(task, res), encoding="utf-8")
                print(f"{task['task_id']}: ACCEPTED after {n} draft(s)")
            else:
                print(f"{task['task_id']}: REJECTED after {n} draft(s): {'; '.join(res['drafts'][-1]['problems'])}")
    print(f"\n{accepted}/{len(tasks)} accepted ({time.time() - t0:.0f} s). Saved in {out}")
    return 0 if accepted == len(tasks) else 1


if __name__ == "__main__":
    sys.exit(main())
