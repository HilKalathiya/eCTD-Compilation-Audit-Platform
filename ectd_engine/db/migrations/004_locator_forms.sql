-- Locator forms grow from 3 to 5 (adds xml=/path and typed=page=N); must accept and refuse the same strings as schema.py.

ALTER TABLE facts DROP CONSTRAINT IF EXISTS facts_locator_form;
ALTER TABLE facts ADD CONSTRAINT facts_locator_form CHECK (
    locator ~ '^row=[0-9]+$'
    OR locator ~ '^page=[0-9]+;box=-?[0-9]+(\.[0-9]+)?,-?[0-9]+(\.[0-9]+)?,-?[0-9]+(\.[0-9]+)?,-?[0-9]+(\.[0-9]+)?$'
    OR locator ~ '^cell=[A-Z]+[0-9]+$'
    OR locator ~ '^xml=/[][A-Za-z0-9_:/@=.''-]+$'
    OR locator ~ '^typed=page=[0-9]+$'
);
