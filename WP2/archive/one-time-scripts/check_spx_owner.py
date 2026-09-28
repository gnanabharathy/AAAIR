"""
check_spx_owner.py

classify_backfill_failures.py detected 23229 matching measurement rows
for nhanes-examination-spx_e-2007, but backfill_dataset_registry.py's
actual registration attempt found 0 to attribute. This checks whether
those rows genuinely don't exist right now, or whether they're already
registered under a DIFFERENT ds_id (the same collision pattern found
earlier between dr1iff_e-2007 and dr1tot_e-2007 in dietary).

Usage: python3 check_spx_owner.py
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

ds_id = "nhanes-examination-spx_e-2007"


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
    "SELECT measurement_id FROM public.measurement "
    "WHERE person_id = ANY(%s) AND measurement_source_value = ANY(%s)",
    (seqns, var_names),
)
meas_ids = [row[0] for row in cur.fetchall()]
print(f"Found {len(meas_ids)} matching measurement rows right now.")

if meas_ids:
    cur.execute(
        "SELECT ds_id, COUNT(*) FROM dataset_row_registry "
        "WHERE table_name = 'measurement' AND row_id = ANY(%s) "
        "GROUP BY ds_id ORDER BY COUNT(*) DESC",
        (meas_ids,),
    )
    owners = cur.fetchall()
    print(f"\nCurrent registry ownership of these {len(meas_ids)} rows:")
    for owner_ds_id, count in owners:
        print(f"  {owner_ds_id}: {count}")
    total_owned = sum(c for _, c in owners)
    print(f"\nTotal owned: {total_owned}, unowned: {len(meas_ids) - total_owned}")
else:
    print("No matching rows exist at all -- classify's earlier count "
          "of 23229 doesn't match current reality. Needs deeper investigation.")

cur.close()
conn.close()
