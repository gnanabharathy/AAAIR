-- create_dataset_row_registry.sql
--
-- Row-level attribution registry: records which ds_id inserted each row
-- into which table. Needed because etl_v2.py writes all datasets into
-- shared person/measurement/observation tables with no attribution
-- column, and person_id (=SEQN) can be shared across several datasets
-- from the same NHANES cycle (though only demographics datasets
-- actually write to person).
--
-- PRIMARY KEY is (table_name, row_id), not row_id alone, since row IDs
-- are only unique within a table, not globally.
--
-- Going forward only -- does NOT retroactively attribute rows already
-- inserted before this table existed.

CREATE TABLE IF NOT EXISTS dataset_row_registry (
    ds_id       VARCHAR(100) NOT NULL,
    table_name  VARCHAR(50)  NOT NULL,
    row_id      INTEGER      NOT NULL,
    loaded_at   TIMESTAMP DEFAULT now(),
    PRIMARY KEY (table_name, row_id)
);

CREATE INDEX IF NOT EXISTS idx_dataset_row_registry_ds_id
    ON dataset_row_registry(ds_id);

SELECT 'dataset_row_registry created' AS status;
