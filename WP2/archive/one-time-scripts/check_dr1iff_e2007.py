"""
check_dr1iff_e2007.py

nhanes-dietary-dr1iff_e-2007 has ZERO entries in dataset_row_registry
(confirmed via direct query), even though it was classified as "ok"
(real data present) by classify_backfill_failures.py earlier. Before
assuming this needs a plain re-backfill, check whether the actual data
exists in measurement/observation at all.

Usage: python3 check_dr1iff_e2007.py
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

cur.execute(
    "SELECT COUNT(*) FROM public.measurement "
    "WHERE person_id = ANY(%s) AND measurement_source_value = ANY(%s)",
    (seqns, var_names),
)
measurement_count = cur.fetchone()[0]

cur.execute(
    "SELECT COUNT(*) FROM public.observation "
    "WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s)",
    (seqns, var_names),
)
observation_count = cur.fetchone()[0]

print(f"SEQNs for {ds_id}: {len(seqns)}")
print(f"Variable names: {len(var_names)}")
print(f"Current measurement rows matching this dataset: {measurement_count}")
print(f"Current observation rows matching this dataset: {observation_count}")

cur.close()
conn.close()
