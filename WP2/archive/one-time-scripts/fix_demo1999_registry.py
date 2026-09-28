"""
fix_demo1999_registry.py

nhanes-demographics-demo-1999's observation registry entries were
found to be 100% orphaned (28412 stale entries pointing at rows
deleted by a crash-interrupted re-run), while the real observation
data (899583 rows, verified by SEQN + variable-name matching) still
exists in the table under different observation_id values that were
never registered.

This deletes the 28412 stale entries and re-registers the real,
currently-existing rows under their actual current observation_id
values. No data is touched -- this only fixes the registry's
bookkeeping to match reality.

Usage: python3 fix_demo1999_registry.py
"""

import json
import os
import urllib.request

import psycopg2
import pyreadstat

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}

ds_id = "nhanes-demographics-demo-1999"


def download_xpt_if_needed(ds_id, entry):
    xpt_path = f"/tmp/{ds_id}.xpt"
    if os.path.exists(xpt_path):
        return xpt_path
    doc_url = entry["url"]
    xpt_url = doc_url.replace(".htm", ".xpt").replace(".html", ".xpt")
    req = urllib.request.Request(xpt_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(xpt_path, "wb") as f:
            f.write(r.read())
    return xpt_path


schema = json.load(open("schema.json"))
entry = schema[ds_id]
xpt_path = download_xpt_if_needed(ds_id, entry)
df, _ = pyreadstat.read_xport(xpt_path, encoding="latin1")
seqns = list(set(int(s) for s in df["SEQN"].dropna().unique()))
var_names = [v["name"] for v in entry.get("variables", [])]

conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = False
cur = conn.cursor()

# Step 1: delete the stale, orphaned registry entries
cur.execute(
    "DELETE FROM dataset_row_registry WHERE ds_id = %s AND table_name = 'observation'",
    (ds_id,),
)
deleted = cur.rowcount
print(f"Deleted {deleted} stale registry entries.")

# Step 2: re-register the real, currently-existing rows
cur.execute(
    "INSERT INTO dataset_row_registry (ds_id, table_name, row_id) "
    "SELECT %s, 'observation', observation_id FROM public.observation "
    "WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s) "
    "ON CONFLICT (table_name, row_id) DO NOTHING",
    (ds_id, seqns, var_names),
)
registered = cur.rowcount
print(f"Registered {registered} real, currently-existing rows.")

conn.commit()
cur.close()
conn.close()
print("Done.")
