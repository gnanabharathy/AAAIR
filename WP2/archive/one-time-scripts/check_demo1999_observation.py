"""
check_demo1999_observation.py

Diagnostic: nhanes-demographics-demo-1999's observation registry
entries (28412 of them) all turned out to be orphaned -- pointing at
observation_id values that no longer exist in the observation table.

Before concluding the data is truly gone, this checks whether the
SAME underlying data might still exist under DIFFERENT (newer)
observation_id values -- e.g. if a safe re-run deleted the old rows
and re-inserted fresh ones, but something interrupted the process
before the new rows got registered.

Matches by: person_id in demo-1999's real SEQN set (re-downloaded from
the actual .xpt) AND observation_source_value in demo-1999's variable
name list -- the same dual-condition matching used by
backfill_dataset_registry.py.

Usage: python3 check_demo1999_observation.py
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
cur = conn.cursor()

cur.execute(
    "SELECT COUNT(*) FROM public.observation "
    "WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s)",
    (seqns, var_names),
)
current_count = cur.fetchone()[0]

print(f"SEQNs for {ds_id}: {len(seqns)}")
print(f"Variable names: {len(var_names)}")
print(f"\nCurrent observation rows matching this dataset (by person_id + "
      f"source_value, regardless of observation_id): {current_count}")
print(f"Originally registered (now orphaned) count was: 28412")

if current_count == 0:
    print("\n=> The data appears to be genuinely GONE, not just re-IDed.")
elif current_count >= 28412:
    print("\n=> The data appears to still exist (likely under NEW "
          "observation_id values from a re-run) -- this is a registry "
          "bookkeeping gap, not real data loss. Re-registering these "
          "rows should fix it.")
else:
    print(f"\n=> Partial match ({current_count} of 28412 expected) -- "
          f"needs closer inspection.")

cur.close()
conn.close()

# --- Refined check: break down by variable name to detect cross-dataset
#     collisions (same variable name reused by other 1999-cycle files
#     sharing the same SEQN pool) that could inflate the naive count above
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute(
    "SELECT observation_source_value, COUNT(*) FROM public.observation "
    "WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s) "
    "GROUP BY observation_source_value ORDER BY COUNT(*) DESC",
    (seqns, var_names),
)
print(f"\n{'='*60}\nBreakdown by variable name (top 20):\n{'='*60}")
rows = cur.fetchall()
for var, count in rows[:20]:
    flag = " <-- suspicious, more than 9965 people" if count > len(seqns) else ""
    print(f"  {var}: {count}{flag}")
print(f"\nTotal distinct variables matched: {len(rows)}")
cur.close()
conn.close()
