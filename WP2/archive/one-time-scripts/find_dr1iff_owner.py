"""
find_dr1iff_owner.py

backfill_dataset_registry.py just reported 0/0/0 attributed for
nhanes-dietary-dr1iff_e-2007, despite 97396 real matching observation
rows existing and 0 registry entries for this exact ds_id (confirmed
separately). Since ON CONFLICT (table_name, row_id) DO NOTHING would
silently skip inserts if these observation_ids are ALREADY registered
under a DIFFERENT ds_id, this finds out who (if anyone) currently owns
them.

Usage: python3 find_dr1iff_owner.py
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

ds_id = "nhanes-dietary-dr1iff_e-2007"


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
cur = conn.cursor()

# Find the actual observation_id values matching this dataset
cur.execute(
    "SELECT observation_id FROM public.observation "
    "WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s)",
    (seqns, var_names),
)
obs_ids = [row[0] for row in cur.fetchall()]
print(f"Found {len(obs_ids)} matching observation_id values.")

# Check who owns these in the registry
cur.execute(
    "SELECT ds_id, COUNT(*) FROM dataset_row_registry "
    "WHERE table_name = 'observation' AND row_id = ANY(%s) "
    "GROUP BY ds_id ORDER BY COUNT(*) DESC",
    (obs_ids,),
)
owners = cur.fetchall()
print(f"\nCurrent registry ownership of these {len(obs_ids)} observation_ids:")
for owner_ds_id, count in owners:
    print(f"  {owner_ds_id}: {count}")

total_owned = sum(c for _, c in owners)
print(f"\nTotal registered (any owner): {total_owned}")
print(f"Total NOT registered by anyone: {len(obs_ids) - total_owned}")

cur.close()
conn.close()
