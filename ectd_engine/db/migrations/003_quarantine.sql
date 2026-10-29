-- Quarantine: rejected candidates are kept with a reason; ectd_app can only call gate_quarantine (no read, no write).
-- Also aligns the non-blank rules with Python: tab/newline-only text is refused too.

DO $$
DECLARE c TEXT;
BEGIN
    FOREACH c IN ARRAY ARRAY['fact_id', 'unit', 'batch', 'test', 'condition', 'doc_id', 'doc_version', 'locator', 'definition']
    LOOP
        EXECUTE format('ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_%s_nonblank', c);
        EXECUTE format('ALTER TABLE facts ADD CONSTRAINT facts_%s_nonblank CHECK (%I ~ ''[^[:space:]]'')', c, c);
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS gate_quarantine_rows (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    fact_id     TEXT,
    batch       TEXT,
    reason_code TEXT NOT NULL CHECK (reason_code ~ '^[A-Z_]+$'),
    reason_text TEXT NOT NULL CHECK (reason_text ~ '[^[:space:]]'),
    candidate   JSONB NOT NULL
);

CREATE OR REPLACE FUNCTION gate_quarantine(
    p_fact_id TEXT, p_batch TEXT, p_reason_code TEXT, p_reason_text TEXT, p_candidate TEXT
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    INSERT INTO gate_quarantine_rows (fact_id, batch, reason_code, reason_text, candidate)
    VALUES (p_fact_id, p_batch, p_reason_code, p_reason_text, p_candidate::jsonb);
END;
$$;

REVOKE ALL ON gate_quarantine_rows FROM PUBLIC, ectd_app;
REVOKE ALL ON FUNCTION gate_quarantine(TEXT, TEXT, TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION gate_quarantine(TEXT, TEXT, TEXT, TEXT, TEXT) TO ectd_app;
