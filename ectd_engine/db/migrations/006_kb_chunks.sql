-- Guideline text chunks for later search. Quotes only: this is NOT the facts table and holds no value column.
CREATE TABLE IF NOT EXISTS kb_chunks (
    chunk_id      TEXT PRIMARY KEY CHECK (chunk_id <> ''),
    doc_id        TEXT NOT NULL CHECK (doc_id <> ''),
    doc_version   TEXT NOT NULL CHECK (doc_version <> ''),
    page          INTEGER NOT NULL CHECK (page >= 1),
    table_id      TEXT CHECK (table_id IS NULL OR table_id ~ '^p[0-9]+-t[0-9]+$'),
    heading_path  TEXT NOT NULL DEFAULT '',
    text          TEXT NOT NULL CHECK (btrim(text) <> ''),
    text_sha256   TEXT NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS kb_chunks_doc_page ON kb_chunks (doc_id, page);

REVOKE ALL ON kb_chunks FROM PUBLIC, ectd_app;
GRANT SELECT ON kb_chunks TO ectd_app;
