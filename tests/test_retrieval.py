"""Live test that guideline search finds the right passage for the brain's 30 gold questions (needs Docker and Ollama)."""
import dataclasses
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

    @classmethod
    def tearDownClass(cls):
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


if __name__ == "__main__":
    unittest.main()
