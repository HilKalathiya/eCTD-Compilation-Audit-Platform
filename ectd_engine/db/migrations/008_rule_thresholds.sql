-- Q3B(R2) threshold rules. A new doc_version adds rows; rows are never changed or removed (trigger below).
CREATE TABLE IF NOT EXISTS rule_thresholds (
    rule_id        TEXT PRIMARY KEY CHECK (rule_id <> ''),
    doc_id         TEXT NOT NULL CHECK (doc_id <> ''),
    doc_version    TEXT NOT NULL CHECK (doc_version <> ''),
    page           INTEGER NOT NULL CHECK (page >= 1),
    kind           TEXT NOT NULL CHECK (kind IN ('reporting', 'identification', 'qualification')),
    dose_low_mg    NUMERIC CHECK (dose_low_mg IS NULL OR dose_low_mg >= 0),
    low_incl       BOOLEAN NOT NULL,
    dose_high_mg   NUMERIC CHECK (dose_high_mg IS NULL OR dose_high_mg > 0),
    high_incl      BOOLEAN NOT NULL,
    percent        NUMERIC NOT NULL CHECK (percent > 0),
    tdi_ug         NUMERIC CHECK (tdi_ug IS NULL OR tdi_ug > 0),
    source_quote   TEXT NOT NULL CHECK (btrim(source_quote) <> ''),
    entered_a_sha  TEXT NOT NULL CHECK (entered_a_sha ~ '^[0-9a-f]{64}$'),
    entered_b_sha  TEXT NOT NULL CHECK (entered_b_sha ~ '^[0-9a-f]{64}$'),
    valid_from     DATE NOT NULL,
    CHECK (dose_low_mg IS NOT NULL OR NOT low_incl),
    CHECK (dose_high_mg IS NOT NULL OR NOT high_incl)
);

CREATE INDEX IF NOT EXISTS rule_thresholds_lookup ON rule_thresholds (doc_id, kind, valid_from);

CREATE OR REPLACE FUNCTION rule_thresholds_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'rule_thresholds is append-only: add a new doc_version instead of changing rows';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rule_thresholds_no_change ON rule_thresholds;
CREATE TRIGGER rule_thresholds_no_change BEFORE UPDATE OR DELETE ON rule_thresholds
    FOR EACH ROW EXECUTE FUNCTION rule_thresholds_append_only();

REVOKE ALL ON rule_thresholds FROM PUBLIC, ectd_app;
GRANT SELECT ON rule_thresholds TO ectd_app;
