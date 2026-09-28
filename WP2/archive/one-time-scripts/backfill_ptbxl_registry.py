"""
backfill_ptbxl_registry.py

Registers every measurement/observation/condition_occurrence/note row
belonging to PTBXL_ecg_records into dataset_row_registry, based on the
person_id range confirmed to be exclusively PTB-XL's (142311-161179,
verified not to overlap any other registered dataset).

Unlike the NHANES backfill (which matches by SEQN + variable name),
this matches purely by person_id range, since:
  - PTB-XL's person_ids are in a range no other dataset uses.
  - Its data spans person/measurement/observation/condition_occurrence/
    note -- more tables than the NHANES pipeline's registry helper
    currently handles.

Usage: python3 backfill_ptbxl_registry.py
"""

import psycopg2

DB_CONFIG = {
    "host": "localhost", "port": 5433, "dbname": "omop",
    "user": "omop_user", "password": "omop_pass",
}
DS_ID = "PTBXL_ecg_records"
PERSON_ID_MIN = 142311
PERSON_ID_MAX = 161179


def register_table(cur, table, id_column):
    cur.execute(
        f"""
        INSERT INTO dataset_row_registry (ds_id, table_name, row_id)
        SELECT %s, %s, {id_column}
        FROM {table}
        WHERE person_id BETWEEN %s AND %s
        ON CONFLICT (table_name, row_id) DO NOTHING
        """,
        (DS_ID, table, PERSON_ID_MIN, PERSON_ID_MAX),
    )
    return cur.rowcount


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    tables = [
        ("person", "person_id"),
        ("measurement", "measurement_id"),
        ("observation", "observation_id"),
        ("condition_occurrence", "condition_occurrence_id"),
        ("note", "note_id"),
    ]

    total = 0
    for table, id_col in tables:
        count = register_table(cur, table, id_col)
        print(f"  {table}: {count} rows registered")
        total += count

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nTotal: {total} rows registered for {DS_ID}.")


if __name__ == "__main__":
    main()
