"""
check_variable_overlap.py

Compares the variable name lists of two datasets (e.g. dr1iff_e-2007
vs dr1tot_e-2007), which is the likely root cause of misattributed
registry entries -- if both files share the same SEQN pool (same
survey cycle) AND some identical variable names, the dual-condition
(SEQN + variable name) matching used by backfill_dataset_registry.py
can't tell which file a given row actually came from.

Also breaks down, for a given misattributed set of observation_ids,
which specific variable names are involved -- this tells us whether
the overlap is total (unrecoverable without re-running real ETL) or
partial (some variables are uniquely identifiable).

Usage:
    python3 check_variable_overlap.py <ds_id_a> <ds_id_b>
"""

import json
import sys

import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}

ds_id_a = sys.argv[1]
ds_id_b = sys.argv[2]

schema = json.load(open("schema.json"))
vars_a = {v["name"] for v in schema[ds_id_a].get("variables", [])}
vars_b = {v["name"] for v in schema[ds_id_b].get("variables", [])}

overlap = vars_a & vars_b
only_a = vars_a - vars_b
only_b = vars_b - vars_a

print(f"{ds_id_a}: {len(vars_a)} variables")
print(f"{ds_id_b}: {len(vars_b)} variables")
print(f"\nOverlapping variable names ({len(overlap)}): {sorted(overlap)}")
print(f"\nOnly in {ds_id_a} ({len(only_a)}): {sorted(only_a)[:20]}{' ...' if len(only_a) > 20 else ''}")
print(f"\nOnly in {ds_id_b} ({len(only_b)}): {sorted(only_b)[:20]}{' ...' if len(only_b) > 20 else ''}")

if overlap:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT observation_source_value, COUNT(*) FROM public.observation "
        "WHERE observation_source_value = ANY(%s) "
        "GROUP BY observation_source_value ORDER BY COUNT(*) DESC",
        (list(overlap),),
    )
    print(f"\n{'='*60}\nRow counts for OVERLAPPING variable names (across ALL person_ids, "
          f"not just this cycle -- for scale reference only):\n{'='*60}")
    for var, count in cur.fetchall():
        print(f"  {var}: {count}")
    cur.close()
    conn.close()
