"""Live test that guideline search finds the right passage for the brain's 30 gold questions (needs Docker and Ollama)."""
import dataclasses
import functools
import json
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from ectd_engine.db import migrate, postgres
from ectd_engine.gate import gate
from ectd_engine.knowledge import embed, load, rerank, search
from tests.test_gate import cand, run
from tests.test_migrate import require_database

GOLD = json.loads((Path(__file__).parent / "gold" / "retrieval_gold.json").read_text(encoding="utf-8"))["questions"]
MIN_RECALL = 0.80
MIN_RERANK = 0.87


def norm(s):
    return " ".join(s.lower().split())


def is_hit(question, quote):
    return quote.doc_id == question["doc_id"] and all(norm(t) in norm(quote.text) for t in question["terms"])


def require_ollama():
    try:
        urllib.request.urlopen(f"{embed.OLLAMA}/api/tags", timeout=5).read()
        embed.embed_query("ping")
    except Exception as e:
        raise AssertionError(f"Ollama or {embed.MODEL} is not reachable ({e!r}); start Ollama and `ollama pull {embed.MODEL}`") from e


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_database()
        require_ollama()
        migrate.migrate()
        cls.conn = postgres.connect()
        load.store(cls.conn, [c for cs in load.build_all().values() for c in cs])
        embed.embed_missing(cls.conn)
        # the same 30 questions are embedded in every mode and test: ask Ollama once per question (vectors are unchanged)
        cls._embed_patch = mock.patch.object(embed, "embed_query", functools.lru_cache(maxsize=None)(embed.embed_query))
        cls._embed_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._embed_patch.stop()
        cls.conn.close()

    def recall(self, mode, show=False):
        """Share of gold questions with a right passage in the top 5; also seconds per query (stored in self.secs)."""
        hits = 0
        start = time.perf_counter()
        for q in GOLD:
            got = search.search(q["q"], 5, self.conn, mode)
            ok = any(is_hit(q, x) for x in got)
            hits += ok
            if show:
                print(f"  {q['id']} {'HIT ' if ok else 'MISS'} {q['doc_id']}  {q['q'][:70]}")
        self.secs = (time.perf_counter() - start) / len(GOLD)
        return hits / len(GOLD)

    def test_recall_at_5(self):
        fts, vec, hybrid = self.recall("fts"), self.recall("vector"), self.recall("hybrid")
        print("rerank per question:")
        rerank = self.recall("rerank", show=True)
        print(f"recall@5 fts={fts:.3f} vector={vec:.3f} hybrid={hybrid:.3f} rerank={rerank:.3f} "
              f"({len(GOLD)} questions); rerank {self.secs:.2f} s per query")
        self.assertGreaterEqual(hybrid, MIN_RECALL)
        self.assertGreaterEqual(rerank, vec)
        self.assertGreaterEqual(rerank, MIN_RERANK)

    def test_planted_reversed_reranker_drops_below_vector(self):
        vec = self.recall("vector")
        with mock.patch.object(rerank, "scores", lambda q, texts: list(range(len(texts)))):
            bad = self.recall("rerank")
        print(f"planted reversed reranker recall@5={bad:.3f} vector={vec:.3f}")
        self.assertLess(bad, vec)

    def test_each_hit_carries_doc_page_table(self):
        got = search.search("identification threshold for degradation products", 5, self.conn)
        self.assertEqual(len(got), 5)
        for x in got:
            self.assertTrue(x.doc_id and x.chunk_id.startswith(x.doc_id) and x.page >= 1 and x.text)
        self.assertEqual([x.score for x in got], sorted((x.score for x in got), reverse=True))

    def test_planted_hit_check_can_fail(self):
        q = dict(GOLD[0], terms=["zzz-not-in-any-guideline"])
        self.assertFalse(any(is_hit(q, x) for x in search.search(q["q"], 5, self.conn)))

    def test_planted_guideline_number_is_not_a_fact(self):
        r, conn = run(cand(source={"doc_id": "Q3B_R2", "doc_version": "Step 4 2006-06-02", "locator": "kb=Q3B_R2:p11-t2"}))
        self.assertNotIsInstance(r, gate.Accepted)
        self.assertEqual(r.reason_code, gate.CONTRACT_INVALID)
        self.assertEqual(conn.kinds(), ["quarantine"])

    def test_quote_has_no_value_field(self):
        names = {f.name for f in dataclasses.fields(search.Quote)}
        self.assertEqual(names, {"chunk_id", "doc_id", "page", "table_id", "text", "score"})
        self.assertFalse(names & {"value", "unit", "number"})


class RerankCacheTests(unittest.TestCase):
    """The score cache must never change the answer; a changed passage, question or model must miss (no database needed)."""
    TEXTS = ["alpha impurity limit", "beta stability data", "gamma dissolution test"]

    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for patcher in (mock.patch.object(rerank, "CACHE_DIR", Path(tmp.name)),
                        mock.patch.object(rerank, "_predict", self.fake_predict)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.calls = []

    def fake_predict(self, question, texts):
        self.calls.append(list(texts))
        return [len(t) / 7 + len(question) / 3 for t in texts]  # deterministic, text-dependent, not round numbers

    def quotes(self, texts):
        return [search.Quote(f"D:p1-c{i}", "D", 1, None, t, 0.0) for i, t in enumerate(texts)]

    def test_cache_hit_returns_same_order_and_scores_without_the_model(self):
        first = rerank.rerank("q?", self.quotes(self.TEXTS), 3)
        n = len(self.calls)
        second = rerank.rerank("q?", self.quotes(self.TEXTS), 3)
        self.assertEqual(len(self.calls), n)  # nothing recomputed
        self.assertEqual(first, second)
        self.assertEqual([x.chunk_id for x in first], [x.chunk_id for x in second])

    def test_planted_changed_passage_is_a_miss(self):
        rerank.scores("q?", self.TEXTS)
        rerank.scores("q?", [self.TEXTS[0], self.TEXTS[1], "gamma dissolution test CHANGED"])
        self.assertEqual(self.calls[-1], ["gamma dissolution test CHANGED"])  # only the changed passage recomputed

    def test_planted_changed_question_is_a_miss(self):
        rerank.scores("q?", self.TEXTS)
        rerank.scores("other question?", self.TEXTS)
        self.assertEqual(self.calls[-1], self.TEXTS)

    def test_planted_changed_model_name_is_a_miss(self):
        rerank.scores("q?", self.TEXTS)
        with mock.patch.object(rerank, "MODEL", "some/other-model"):
            rerank.scores("q?", self.TEXTS)
        self.assertEqual(self.calls[-1], self.TEXTS)

    def test_planted_changed_version_is_a_miss(self):
        rerank.scores("q?", self.TEXTS)
        with mock.patch.object(rerank, "VERSION", "2"):
            rerank.scores("q?", self.TEXTS)
        self.assertEqual(self.calls[-1], self.TEXTS)

    def test_corrupt_cache_entry_is_recomputed(self):
        rerank.scores("q?", self.TEXTS)
        next(rerank.CACHE_DIR.iterdir()).write_text("not a number", encoding="ascii")
        again = rerank.scores("q?", self.TEXTS)
        self.assertEqual(again, self.fake_predict("q?", self.TEXTS))


class RerankLiveTests(unittest.TestCase):
    """The real model, with the disk cache switched off, so a broken model or setup cannot hide behind cached scores."""

    def test_live_model_ranks_the_obvious_pair_first(self):
        import tempfile
        question = "What is the identification threshold for degradation products?"
        good = "The identification threshold for a degradation product in a new drug product is 0.2% for a daily dose of 10 mg to 2 g."
        bad = "The committee meeting was held in November and the minutes were circulated to all members afterwards."
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(rerank, "CACHE_DIR", Path(tmp)):
            first = rerank.scores(question, [bad, good])
            self.assertEqual(len(list(Path(tmp).iterdir())), 2)  # both pairs were really scored, none read from the old cache
        self.assertGreater(first[1], first[0])
        self.assertEqual(max(range(2), key=lambda i: first[i]), 1)


if __name__ == "__main__":
    unittest.main()
