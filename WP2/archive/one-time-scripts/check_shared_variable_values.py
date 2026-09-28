"""
check_shared_variable_values.py

Before assuming that overlapping variable names (e.g. DRDINT shared
between DR1IFF and DR1TOT) point at genuinely IDENTICAL data, this
checks: for a handful of specific people, what does the observation
table actually contain for that variable name -- one row, or multiple
rows? And if multiple, do they have the SAME value or DIFFERENT
values?

This directly answers: is this "one physical fact shared by two
files" (safe to co-register), or "two files each independently
recorded their own possibly-different value under the same variable
name" (NOT safe to treat as one shared row)?

Usage: python3 check_shared_variable_values.py <variable_name> <n_people>
"""

import sys
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}

var_name = sys.argv[1] if len(sys.argv) > 1 else "DRDINT"
n_people = int(sys.argv[2]) if len(sys.argv) > 2 else 5

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Pick a handful of person_ids that have this variable recorded
cur.execute(
    "SELECT DISTINCT person_id FROM public.observation "
    "WHERE observation_source_value = %s LIMIT %s",
    (var_name, n_people),
)
person_ids = [row[0] for row in cur.fetchall()]

print(f"Checking variable '{var_name}' for {len(person_ids)} sample people:\n")

for pid in person_ids:
    cur.execute(
        "SELECT observation_id, value_as_number, value_as_string, observation_date "
        "FROM public.observation "
        "WHERE person_id = %s AND observation_source_value = %s "
        "ORDER BY observation_id",
        (pid, var_name),
    )
    rows = cur.fetchall()
    print(f"person_id={pid}: {len(rows)} row(s)")
    for obs_id, val_num, val_str, obs_date in rows:
        print(f"    observation_id={obs_id}  value_as_number={val_num}  "
              f"value_as_string={val_str}  date={obs_date}")
    print()

cur.close()
conn.close()
