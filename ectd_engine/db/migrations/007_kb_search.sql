-- Search columns for guideline chunks: a word index (full-text) and a meaning index (768-number vectors). Still quotes only.
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS fts tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX IF NOT EXISTS kb_chunks_fts ON kb_chunks USING GIN (fts);

ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS embedding vector(768);
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS embedding_sha256 TEXT CHECK (embedding_sha256 IS NULL OR embedding_sha256 ~ '^[0-9a-f]{64}$');
CREATE INDEX IF NOT EXISTS kb_chunks_embedding ON kb_chunks USING hnsw (embedding vector_cosine_ops);
