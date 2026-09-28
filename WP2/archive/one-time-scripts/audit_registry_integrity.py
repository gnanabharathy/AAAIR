"""
audit_registry_integrity.py

After discovering that nhanes-demographics-demo-1999's ENTIRE
observation registry (28412 entries) was orphaned -- pointing at
observation_id values no longer in the real table, apparently from a
crash that hit between a safe re-run's DELETE and its subsequent
INSERT+registration -- this audits ALL currently-registered ds_ids to
see how widespread the problem is.

For each ds_id + table_name combination currently in
dataset_row_registry, this reports:
  - total registered rows
  - how many are orphaned (row_id no longer exists in the real table)
  - orphan percentage

A clean dataset should show 0% orphaned. Datasets near 100% orphaned
are the ones most likely affected by the same crash-timing issue as
demo-1999 and need re-registration.

Usage: python3 audit_registry_integrity.py
"""

import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}

TABLE_ID_COLUMNS = {
    "person": "person_id",
    "measurement": "measurement_id",
    "observation": "observation_id",
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

cur.execute(
    "SELECT ds_id, table_name, COUNT(*) FROM dataset_row_registry "
    "GROUP BY ds_id, table_name ORDER BY ds_id, table_name"
)
combos = cur.fetchall()

print(f"{'ds_id':<45} {'table':<13} {'total':>10} {'orphaned':>10} {'pct':>7}")
print("-" * 90)

flagged = []
for ds_id, table_name, total in combos:
    id_col = TABLE_ID_COLUMNS.get(table_name)
    if not id_col:
        continue
    cur.execute(
        f"SELECT COUNT(*) FROM dataset_row_registry r "
        f"LEFT JOIN public.{table_name} t ON r.row_id = t.{id_col} "
        f"WHERE r.ds_id = %s AND r.table_name = %s AND t.{id_col} IS NULL",
        (ds_id, table_name),
    )
    orphaned = cur.fetchone()[0]
    pct = (orphaned / total * 100) if total else 0
    marker = ""
    if pct > 50:
        marker = "  <-- HIGH ORPHAN RATE"
        flagged.append((ds_id, table_name, total, orphaned, pct))
    print(f"{ds_id:<45} {table_name:<13} {total:>10} {orphaned:>10} {pct:>6.1f}%{marker}")

cur.close()
conn.close()

print(f"\n{'='*90}")
print(f"Flagged (>50% orphaned): {len(flagged)} dataset/table combinations")
for ds_id, table_name, total, orphaned, pct in flagged:
    print(f"  {ds_id} / {table_name}: {orphaned}/{total} ({pct:.1f}%)")
