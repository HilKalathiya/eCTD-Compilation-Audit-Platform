"""Turns guideline chunks into meaning-vectors with Ollama's embeddinggemma and stores them, skipping chunks already done."""
import argparse
import json
import urllib.request

OLLAMA = "http://localhost:11434"
MODEL = "embeddinggemma"
DIM = 768
BATCH = 16


def _post(texts):
    req = urllib.request.Request(f"{OLLAMA}/api/embed", data=json.dumps({"model": MODEL, "input": texts}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        vecs = json.load(r)["embeddings"]
    if len(vecs) != len(texts) or any(len(v) != DIM for v in vecs):
        raise RuntimeError(f"embeddinggemma returned wrong shape (wanted {len(texts)} x {DIM})")
    return vecs


def embed_query(q):
    """One question -> one vector (uses the model's search-query prefix)."""
    return _post([f"task: search result | query: {q}"])[0]


def embed_documents(texts):
    """Guideline texts -> vectors (uses the model's document prefix)."""
    return _post([f"title: none | text: {t}" for t in texts])


def vec_literal(v):
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


def embed_missing(conn):
    """Embed every chunk whose stored vector is missing or was made from older text (cache key = text sha256). Returns count."""
    rows = conn.execute("SELECT chunk_id, text, text_sha256 FROM kb_chunks "
                        "WHERE embedding IS NULL OR embedding_sha256 IS DISTINCT FROM text_sha256 ORDER BY chunk_id").fetchall()
    for i in range(0, len(rows), BATCH):
        part = rows[i:i + BATCH]
        for (cid, _, sha), v in zip(part, embed_documents([r[1] for r in part])):
            conn.execute("UPDATE kb_chunks SET embedding = %s::vector, embedding_sha256 = %s WHERE chunk_id = %s",
                         (vec_literal(v), sha, cid))
        conn.commit()
    return len(rows)


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    from ectd_engine.db import migrate, postgres
    migrate.migrate()
    conn = postgres.connect()
    try:
        print(f"embedded {embed_missing(conn)} chunks")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
