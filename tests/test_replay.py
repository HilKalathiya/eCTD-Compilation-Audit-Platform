"""Tests that tools/replay.py compares validators correctly and fails loudly when it should."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import replay  # noqa: E402


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.tasks = replay.load_tasks()
        self.files = [self.dir / "a.jsonl", self.dir / "b.jsonl"]
        # one fixture of each file shape: audit row (raw_draft) and drafts row (text)
        write_jsonl(self.files[0], [
            {"task_id": "lt_assay", "draft": 1, "raw_draft": "Assay was stable."},
            {"task_id": "lt_water", "draft": 2, "raw_draft": ""}])
        write_jsonl(self.files[1], [{"task_id": "acc_assay", "draft": 1, "text": "Assay is 99.1%."}])
        self.out = self.dir / "replay.csv"

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, port=None, files=None):
        return replay.main(files=files or self.files, tasks=self.tasks, out=self.out,
                           frozen=replay.load_frozen(), port=port or replay.load_port())

    def test_same_verdicts_on_fixtures(self):
        self.assertEqual(self.run_main(), 0)
        rows = self.out.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 1 + 3)
        self.assertNotIn(",no", "\n".join(r[-3:] for r in rows[1:]))

    def test_summary_line(self):
        res = replay.replay(replay.load_drafts(self.files), self.tasks, replay.load_frozen(), replay.load_port())
        self.assertEqual(replay.summary(res), "3 drafts, 3 same, 0 different")

    def test_planted_flipped_verdict_is_reported_and_exit_nonzero(self):
        real = replay.load_port()

        class Flip(replay.Judge):
            n = 0

            def verdict(self, task, text):
                v, p = real.verdict(task, text)
                Flip.n += 1
                if Flip.n == 1:  # flip exactly one verdict
                    return ("accepted", []) if v != "accepted" else ("rejected", ["planted"])
                return v, p

        stub = Flip(real.compute_facts, real.validate, real.render, real.verify_render)
        self.assertEqual(self.run_main(port=stub), 1)
        Flip.n = 0
        res = replay.replay(replay.load_drafts(self.files), self.tasks, replay.load_frozen(),
                            Flip(real.compute_facts, real.validate, real.render, real.verify_render))
        self.assertEqual(replay.summary(res), "3 drafts, 2 same, 1 different")

    def test_missing_draft_file_is_a_clear_error_not_zero_pass(self):
        code = self.run_main(files=[self.files[0], self.dir / "nope.jsonl"])
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())
        with self.assertRaises(replay.ReplayError):
            replay.load_drafts([self.dir / "nope.jsonl"])

    def test_empty_draft_file_is_an_error(self):
        empty = self.dir / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        self.assertEqual(self.run_main(files=[empty]), 2)

    def test_unknown_task_is_an_error(self):
        write_jsonl(self.files[0], [{"task_id": "zzz", "draft": 1, "raw_draft": "x"}])
        self.assertEqual(self.run_main(), 2)


if __name__ == "__main__":
    unittest.main()
