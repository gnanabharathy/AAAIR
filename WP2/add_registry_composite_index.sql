-- add_registry_composite_index.sql
--
-- generate_dataset_view_schema.py's isolation views filter with:
--   WHERE row_id IN (SELECT row_id FROM dataset_row_registry
--                     WHERE ds_id = ... AND table_name = ...)
--
-- The existing indexes don't serve this well at scale:
--   - PRIMARY KEY (table_name, row_id) -- doesn't lead with ds_id
--   - idx_dataset_row_registry_ds_id (ds_id) -- single-column, still
--     needs a row-by-row table_name filter on the matched rows
--
-- At small row counts (a few thousand, as in early demographics
-- testing) this was fast enough to not notice. At ~50 million rows
-- (after dietary backfill), it became the bottleneck causing a single
-- dataset's DQD run to take 1.5+ hours instead of minutes.
--
-- This composite index lets Postgres satisfy the (ds_id, table_name)
-- filter directly from the index, which is exactly the isolation
-- view's access pattern.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dataset_row_registry_ds_id_table_name
    ON dataset_row_registry (ds_id, table_name);

SELECT 'index created' AS status;
