"""Checks the guideline chunks and stores them in the kb_chunks table (or just counts them with --dry-run)."""
import argparse
import re

import fitz  # PyMuPDF

from ectd_engine.knowledge import chunk as ch

REQUIRED = ("chunk_id", "doc_id", "doc_version", "page", "text", "sha256")
TABLE_ID_RE = re.compile(r"^p\d+-t\d+$")


class BadChunk(ValueError):
    """A chunk is missing its document, version, page or text, or its page is outside the PDF."""


def validate(c, pages=None):
    """Refuse a chunk with no document/version, page below 1 (or past the last page), empty text, or a wrong hash."""
    for key in REQUIRED:
        if c.get(key) in (None, ""):
            raise BadChunk(f"{c.get('chunk_id')}: missing {key}")
    if not isinstance(c["page"], int) or c["page"] < 1 or (pages and c["page"] > pages):
        raise BadChunk(f"{c['chunk_id']}: page {c['page']!r} not in 1..{pages}")
    if not c["text"].strip():
        raise BadChunk(f"{c['chunk_id']}: empty text")
    if c["table_id"] is not None and not TABLE_ID_RE.match(c["table_id"]):
        raise BadChunk(f"{c['chunk_id']}: bad table_id {c['table_id']!r}")
    if ch.sha(c["text"]) != c["sha256"]:
        raise BadChunk(f"{c['chunk_id']}: sha256 does not match text")


def build_all():
    """Chunk every guideline and validate each chunk -> {doc_id: [chunk, ...]}."""
    out = {}
    for doc_id, name in ch.DOCS.items():
        pages = len(fitz.open(ch.ICH_DIR / name))
        out[doc_id] = ch.chunk_document(doc_id)
        for c in out[doc_id]:
            validate(c, pages)
    return out


SQL = ("INSERT INTO kb_chunks (chunk_id, doc_id, doc_version, page, table_id, heading_path, text, text_sha256) "
       "VALUES (%(chunk_id)s, %(doc_id)s, %(doc_version)s, %(page)s, %(table_id)s, %(heading_path)s, %(text)s, %(sha256)s) "
       "ON CONFLICT (chunk_id) DO UPDATE SET doc_version = EXCLUDED.doc_version, page = EXCLUDED.page, "
       "table_id = EXCLUDED.table_id, heading_path = EXCLUDED.heading_path, text = EXCLUDED.text, "
       "text_sha256 = EXCLUDED.text_sha256 WHERE kb_chunks.text_sha256 <> EXCLUDED.text_sha256")


def store(conn, chunks):
    """Insert chunks; a chunk_id already stored is skipped (or updated if its text changed). Returns the chunk count sent."""
    for c in chunks:
        conn.execute(SQL, c)
    conn.commit()
    return len(chunks)


def summary(by_doc):
    lines = []
    for doc_id, cs in by_doc.items():
        tables = sum(1 for c in cs if c["table_id"])
        lines.append(f"{doc_id} ({cs[0]['doc_version']}): {len(cs)} chunks, {tables} table chunks")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print chunk counts per document; store nothing")
    args = ap.parse_args(argv)
    by_doc = build_all()
    print("\n".join(summary(by_doc)))
    if args.dry_run:
        return
    from ectd_engine.db import migrate, postgres
    migrate.migrate()
    conn = postgres.connect()
    try:
        n = sum(store(conn, cs) for cs in by_doc.values())
    finally:
        conn.close()
    print(f"stored {n} chunks")


if __name__ == "__main__":
    main()
