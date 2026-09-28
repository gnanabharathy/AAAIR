-- create_shared_row_registry.sql
--
-- dataset_row_registry's PRIMARY KEY (table_name, row_id) enforces
-- "one owner per row" -- required for etl_v3.py's safe-DELETE logic
-- on person/measurement/observation (only the ds_id that owns a row
-- may delete it on rerun). That invariant must stay intact.
--
-- But some rows are GENUINELY shared: e.g. DR1IFF (individual food
-- records) and DR1TOT (daily nutrient totals) files both legitimately
-- contain metadata variables like DRDINT/WTDRD1/DR1LANG -- the same
-- underlying observation row is truly "owned" by neither exclusively.
--
-- This table lets MULTIPLE ds_ids reference the same row for
-- isolated-view/DQD purposes, without granting any of them delete
-- rights over it (that stays governed by dataset_row_registry alone).

CREATE TABLE IF NOT EXISTS shared_row_registry (
    ds_id       VARCHAR(100) NOT NULL,
    table_name  VARCHAR(50)  NOT NULL,
    row_id      INTEGER      NOT NULL,
    loaded_at   TIMESTAMP DEFAULT now(),
    PRIMARY KEY (ds_id, table_name, row_id)
);

CREATE INDEX IF NOT EXISTS idx_shared_row_registry_ds_id_table_name
    ON shared_row_registry (ds_id, table_name);

SELECT 'shared_row_registry created' AS status;
