"""Live test that guideline search finds the right passage for the brain's 30 gold questions (needs Docker and Ollama)."""
import dataclasses
import json
import unittest
import urllib.request
from pathlib import Path

from ectd_engine.db import migrate, postgres
from ectd_engine.gate import gate
from ectd_engine.knowledge import embed, load, search
from tests.test_gate import cand, run
from tests.test_migrate import require_database

GOLD = json.loads((Path(__file__).parent / "gold" / "retrieval_gold.json").read_text(encoding="utf-8"))["questions"]
MIN_RECALL = 0.80


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
        hits = 0
        for q in GOLD:
            got = search.search(q["q"], 5, self.conn, mode)
            ok = any(is_hit(q, x) for x in got)
            hits += ok
            if show:
                print(f"  {q['id']} {'HIT ' if ok else 'MISS'} {q['doc_id']}  {q['q'][:70]}")
        return hits / len(GOLD)

    def test_recall_at_5(self):
        hybrid = self.recall("hybrid", show=True)
        fts, vec = self.recall("fts"), self.recall("vector")
        print(f"recall@5 hybrid={hybrid:.3f} fts-only={fts:.3f} vector-only={vec:.3f} ({len(GOLD)} questions)")
        self.assertGreaterEqual(hybrid, MIN_RECALL)

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
