-- create_concept_dataset_registry.sql
--
-- A SEPARATE table from dataset_row_registry, purpose-built for the
-- concept table's many-to-many attribution needs.
--
-- dataset_row_registry's PRIMARY KEY (table_name, row_id) enforces
-- "each row has exactly one legitimate owner dataset" -- a property
-- that etl_v2.py's safe-DELETE logic depends on for person/
-- measurement/observation (only the ds_id that originally wrote a row
-- may delete it on rerun). That single-owner invariant must NOT be
-- relaxed.
--
-- But concept table rows are shared reference data: the same
-- concept_id (e.g. a USDA food code) is legitimately referenced by
-- MANY different NHANES survey-year datasets. This needs a genuine
-- many-to-many relationship, which is a different concern from
-- dataset_row_registry's "who owns this row" semantics -- hence a
-- separate table rather than relaxing the existing one.

CREATE TABLE IF NOT EXISTS concept_dataset_registry (
    ds_id       VARCHAR(100) NOT NULL,
    concept_id  INTEGER      NOT NULL,
    loaded_at   TIMESTAMP DEFAULT now(),
    PRIMARY KEY (ds_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_concept_dataset_registry_concept_id
    ON concept_dataset_registry(concept_id);

SELECT 'concept_dataset_registry created' AS status;
