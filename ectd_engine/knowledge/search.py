"""Finds guideline passages for a question by mixing word search and meaning search (reciprocal rank fusion)."""
import re
from dataclasses import dataclass

from ectd_engine.knowledge import embed

RRF_K = 60
POOL = 20
RERANK_POOL = 12  # per side; 12 + 12 candidates keeps CPU reranking near 10 s per question
WORD_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class Quote:
    """A guideline passage with where it came from. Text only: no numeric value, so it can never become a fact."""
    chunk_id: str
    doc_id: str
    page: int
    table_id: "str | None"
    text: str
    score: float


COLS = "chunk_id, doc_id, page, table_id, text"
FTS_SQL = (f"SELECT {COLS} FROM kb_chunks, to_tsquery('english', %s) q WHERE fts @@ q "
           "ORDER BY ts_rank_cd(fts, q) DESC, chunk_id LIMIT %s")
VEC_SQL = f"SELECT {COLS} FROM kb_chunks WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s"


def fts_hits(conn, q, n=POOL):
    """Rows matching ANY question word (stop-words dropped by Postgres), best rank first."""
    words = WORD_RE.findall(q.lower())
    if not words:
        return []
    return conn.execute(FTS_SQL, (" | ".join(words), n)).fetchall()


def vector_hits(conn, q, n=POOL):
    return conn.execute(VEC_SQL, (embed.vec_literal(embed.embed_query(q)), n)).fetchall()


def fuse(lists, k=5):
    """Reciprocal rank fusion: each list gives 1/(60+rank) to a row; sum, sort. Returns Quotes."""
    score, rows = {}, {}
    for hits in lists:
        for rank, row in enumerate(hits, 1):
            score[row[0]] = score.get(row[0], 0.0) + 1.0 / (RRF_K + rank)
            rows[row[0]] = row
    best = sorted(score, key=lambda cid: (-score[cid], cid))[:k]
    return [Quote(*rows[cid], score[cid]) for cid in best]


def search(q, k=5, conn=None, mode="hybrid"):
    """Top-k Quotes for a question. mode 'fts' or 'vector' runs one side only (for measuring); 'rerank' re-reads the top 12 of each side (up to 24 passages)."""
    own = conn is None
    if own:
        from ectd_engine.db import postgres
        conn = postgres.connect()
    try:
        n = RERANK_POOL if mode == "rerank" else POOL
        lists = []
        if mode in ("hybrid", "fts", "rerank"):
            lists.append(fts_hits(conn, q, n))
        if mode in ("hybrid", "vector", "rerank"):
            lists.append(vector_hits(conn, q, n))
        if mode == "rerank":
            from ectd_engine.knowledge import rerank
            return rerank.rerank(q, fuse(lists, 2 * n), k)
        return fuse(lists, k)
    finally:
        if own:
            conn.close()
