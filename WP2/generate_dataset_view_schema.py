"""
generate_dataset_view_schema.py

Given a ds_id, generates an isolated schema of filtered views based on
dataset_row_registry -- the general, automated replacement for the
hand-written create_ptbxl_view_schema.sql.

For each table the dataset actually touched (found via
dataset_row_registry), creates a view filtered to just that dataset's
rows: WHERE <table>_id IN (SELECT row_id FROM dataset_row_registry
WHERE ds_id = ... AND table_name = ...).

For every other base table in public that DQD's standard check set
might reference, creates an empty passthrough view (WHERE false),
discovered dynamically from information_schema.tables -- avoids the
whack-a-mole missing-table problem from the hand-written version
(CONDITION_ERA was missed there).

Reference/vocabulary tables pass through unfiltered.

Usage:
    python3 generate_dataset_view_schema.py <ds_id>

Output: creates a schema named dqd_view_<sanitized ds_id> and prints
the schema name to use as dqd.R's third argument.
"""

import re
import sys

import psycopg2
from psycopg2 import sql

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}

REFERENCE_TABLES = [
    "concept", "concept_ancestor", "concept_class", "concept_relationship",
    "concept_synonym", "domain", "drug_strength", "relationship",
    "vocabulary", "source_to_concept_map",
    # Administrative/instance-level metadata, not per-dataset patient
    # data -- DataQualityDashboard requires cdm_source to be non-empty
    # to run at all, so these must never be filtered down to nothing.
    "cdm_source", "care_site", "location", "provider",
]


def sanitize_schema_name(ds_id):
    """Turn a ds_id like 'nhanes-examination-vix-1999' into a valid
    Postgres schema identifier."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", ds_id)
    if name[0].isdigit():
        name = "_" + name
    return f"dqd_view_{name}"


def get_registered_tables(cur, ds_id):
    """Which tables does this ds_id actually have rows in?"""
    cur.execute(
        "SELECT DISTINCT table_name FROM dataset_row_registry WHERE ds_id = %s",
        (ds_id,),
    )
    return [row[0] for row in cur.fetchall()]


def get_all_public_base_tables(cur):
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    )
    return [row[0] for row in cur.fetchall()]


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_dataset_view_schema.py <ds_id>")
        sys.exit(1)

    ds_id = sys.argv[1]
    schema_name = sanitize_schema_name(ds_id)

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    registered_tables = get_registered_tables(cur, ds_id)
    if not registered_tables:
        print(f"WARNING: no rows found in dataset_row_registry for ds_id='{ds_id}'. "
              f"Either this dataset hasn't been ETL'd with the registry-aware "
              f"etl_v3.py, or the ds_id is misspelled. Aborting.")
        sys.exit(1)

    print(f"ds_id '{ds_id}' has registered rows in: {registered_tables}")

    all_tables = get_all_public_base_tables(cur)

    cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema_name)))
    cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))

    for table_name in all_tables:
        view_ident = sql.Identifier(schema_name, table_name)
        source_ident = sql.Identifier("public", table_name)

        if table_name == "dataset_row_registry":
            continue  # never expose our own bookkeeping table to DQD

        if table_name in registered_tables:
            id_column = f"{table_name}_id"
            cur.execute(
                sql.SQL(
                    "CREATE VIEW {view} AS SELECT t.* FROM {source} t "
                    "WHERE t.{id_col} IN ("
                    "SELECT row_id FROM public.dataset_row_registry "
                    "WHERE ds_id = %s AND table_name = %s)"
                ).format(
                    view=view_ident,
                    source=source_ident,
                    id_col=sql.Identifier(id_column),
                ),
                (ds_id, table_name),
            )
        elif table_name in REFERENCE_TABLES:
            cur.execute(
                sql.SQL("CREATE VIEW {view} AS SELECT * FROM {source}").format(
                    view=view_ident, source=source_ident
                )
            )
        else:
            cur.execute(
                sql.SQL("CREATE VIEW {view} AS SELECT * FROM {source} WHERE false").format(
                    view=view_ident, source=source_ident
                )
            )

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nCreated schema '{schema_name}' with {len(all_tables)} views "
          f"({len(registered_tables)} filtered to this dataset, "
          f"{len(REFERENCE_TABLES)} reference tables passed through, "
          f"rest empty).")
    print(f"\nRun DQD scoped to just this dataset with:")
    print(f'  Rscript dqd.R "{ds_id}" "<display name>" {schema_name}')


if __name__ == "__main__":
    main()
