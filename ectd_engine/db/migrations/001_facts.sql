-- Fact store: one table, one door (gate_insert_fact). The role ectd_app is created by migrate.py before this runs.

CREATE TABLE IF NOT EXISTS facts (
    fact_id     TEXT PRIMARY KEY,
    value       NUMERIC NOT NULL,
    value_text  TEXT NOT NULL,
    unit        TEXT NOT NULL,
    batch       TEXT NOT NULL,
    test        TEXT NOT NULL,
    condition   TEXT NOT NULL,
    month       INTEGER CHECK (month IS NULL OR month >= 0),
    doc_id      TEXT NOT NULL,
    doc_version TEXT NOT NULL,
    locator     TEXT NOT NULL,
    lineage     TEXT NOT NULL CHECK (lineage IN ('original', 'copy', 'unknown')),
    definition  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (value_text = value::text)
);

CREATE OR REPLACE FUNCTION gate_insert_fact(
    p_fact_id TEXT, p_value NUMERIC, p_value_text TEXT, p_unit TEXT, p_batch TEXT,
    p_test TEXT, p_condition TEXT, p_month INTEGER, p_doc_id TEXT, p_doc_version TEXT,
    p_locator TEXT, p_lineage TEXT, p_definition TEXT
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF p_value_text IS DISTINCT FROM p_value::text THEN
        RAISE EXCEPTION 'gate: value_text % does not equal the text of value %', p_value_text, p_value::text
            USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (SELECT 1 FROM facts WHERE fact_id = p_fact_id) THEN
        RAISE EXCEPTION 'gate: fact_id % already exists (facts are append-only)', p_fact_id
            USING ERRCODE = 'unique_violation';
    END IF;
    INSERT INTO facts (fact_id, value, value_text, unit, batch, test, condition, month,
                       doc_id, doc_version, locator, lineage, definition)
    VALUES (p_fact_id, p_value, p_value_text, p_unit, p_batch, p_test, p_condition, p_month,
            p_doc_id, p_doc_version, p_locator, p_lineage, p_definition);
END;
$$;

REVOKE ALL ON facts FROM PUBLIC, ectd_app;
REVOKE ALL ON FUNCTION gate_insert_fact(TEXT, NUMERIC, TEXT, TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT SELECT ON facts TO ectd_app;
GRANT EXECUTE ON FUNCTION gate_insert_fact(TEXT, NUMERIC, TEXT, TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT) TO ectd_app;
