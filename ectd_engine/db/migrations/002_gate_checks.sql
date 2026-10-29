-- Table-level rules mirroring schema.py, so the database refuses bad facts even if Python is skipped.

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_fact_id_nonblank;
ALTER TABLE facts ADD CONSTRAINT facts_fact_id_nonblank CHECK (btrim(fact_id) <> '');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_unit_nonblank;
ALTER TABLE facts ADD CONSTRAINT facts_unit_nonblank CHECK (btrim(unit) <> '');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_batch_nonblank;
ALTER TABLE facts ADD CONSTRAINT facts_batch_nonblank CHECK (btrim(batch) <> '');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_test_nonblank;
ALTER TABLE facts ADD CONSTRAINT facts_test_nonblank CHECK (btrim(test) <> '');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_condition_nonblank;
ALTER TABLE facts ADD CONSTRAINT facts_condition_nonblank CHECK (btrim(condition) <> '');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_doc_id_nonblank;
ALTER TABLE facts ADD CONSTRAINT facts_doc_id_nonblank CHECK (btrim(doc_id) <> '');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_doc_version_nonblank;
ALTER TABLE facts ADD CONSTRAINT facts_doc_version_nonblank CHECK (btrim(doc_version) <> '');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_locator_nonblank;
ALTER TABLE facts ADD CONSTRAINT facts_locator_nonblank CHECK (btrim(locator) <> '');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_definition_nonblank;
ALTER TABLE facts ADD CONSTRAINT facts_definition_nonblank CHECK (btrim(definition) <> '');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_value_finite;
ALTER TABLE facts ADD CONSTRAINT facts_value_finite CHECK (value <> 'NaN' AND value <> 'Infinity' AND value <> '-Infinity');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_value_plain_text;
ALTER TABLE facts ADD CONSTRAINT facts_value_plain_text CHECK (value_text ~ '^-?[0-9]+(\.[0-9]+)?$');

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_month_check;
ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_month_nonneg;
ALTER TABLE facts ADD CONSTRAINT facts_month_nonneg CHECK (month IS NULL OR month >= 0);

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_lineage_check;
ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_lineage_allowed;
ALTER TABLE facts ADD CONSTRAINT facts_lineage_allowed CHECK (lineage IN ('original', 'copy', 'unknown'));

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_locator_form;
ALTER TABLE facts ADD CONSTRAINT facts_locator_form CHECK (locator ~ '^row=[0-9]+$' OR locator ~ '^page=[0-9]+;box=-?[0-9]+(\.[0-9]+)?,-?[0-9]+(\.[0-9]+)?,-?[0-9]+(\.[0-9]+)?,-?[0-9]+(\.[0-9]+)?$' OR locator ~ '^cell=[A-Z]+[0-9]+$');
