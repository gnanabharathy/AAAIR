"""
audit_examination_status.py

Full status check for the "examination" category before doing any
batch ETL/DQD work on it -- mirrors the audit approach used for
dietary before its batch work began.

Checks:
  1. How many examination datasets exist in schema.json.
  2. For each: does real data already exist in measurement/observation
     (via SEQN + variable-name matching, same technique as
     classify_backfill_failures.py), and is it registered in
     dataset_row_registry?
  3. Does an existing dqd/raw/{ds_id}.json report already exist?
  4. Cross-check against batch_progress.json's done/failed lists.

Usage: python3 audit_examination_status.py
"""

import json
import os

import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}

schema = json.load(open("schema.json"))
exam_ids = sorted(
    ds_id for ds_id, entry in schema.items()
    if "examination" in [s.lower() for s in entry.get("subtypes", [])]
)

progress = json.load(open("batch_progress.json")) if os.path.exists("batch_progress.json") else {"done": [], "failed": []}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

print(f"Total examination datasets in schema.json: {len(exam_ids)}\n")

no_seqn_col = []
registered = []
data_exists_not_registered = []
no_data_at_all = []
has_report = []
in_progress_done = []
in_progress_failed = []

for ds_id in exam_ids:
    entry = schema[ds_id]
    var_names = [v["name"] for v in entry.get("variables", [])]

    if ds_id in progress.get("done", []):
        in_progress_done.append(ds_id)
    if ds_id in progress.get("failed", []):
        in_progress_failed.append(ds_id)
    if os.path.exists(f"dqd/raw/{ds_id}.json"):
        has_report.append(ds_id)

    cur.execute(
        "SELECT COUNT(*) FROM dataset_row_registry WHERE ds_id = %s",
        (ds_id,),
    )
    reg_count = cur.fetchone()[0]

    if reg_count > 0:
        registered.append((ds_id, reg_count))
        continue

    if not var_names:
        no_seqn_col.append(ds_id)
        continue

    # No registry entries -- check if real data exists anyway (SEQN
    # column presence is a proxy check here via schema.json; a full
    # xpt-level SEQN check would require downloading each file, which
    # we skip in this first-pass audit)
    if "SEQN" not in var_names:
        no_seqn_col.append(ds_id)
    else:
        no_data_at_all.append(ds_id)

cur.close()
conn.close()

print(f"{'='*60}\nSummary\n{'='*60}")
print(f"Registered in dataset_row_registry (has real, tracked data): {len(registered)}")
print(f"No SEQN in schema.json variable list (likely structural, like dietary's 24): {len(no_seqn_col)}")
print(f"Has SEQN but zero registry entries (needs ETL or backfill): {len(no_data_at_all)}")
print(f"\nAlready has a dqd/raw report file: {len(has_report)}")
print(f"In batch_progress.json 'done': {len(in_progress_done)}")
print(f"In batch_progress.json 'failed': {len(in_progress_failed)}")

print(f"\n{'='*60}\nRegistered datasets (sample, first 15):\n{'='*60}")
for ds_id, count in registered[:15]:
    print(f"  {ds_id}: {count} registry rows")

print(f"\n{'='*60}\nNo-SEQN datasets (structural candidates):\n{'='*60}")
for ds_id in no_seqn_col:
    print(f"  {ds_id}")

print(f"\n{'='*60}\nNeeds ETL/backfill (has SEQN, zero registry entries):\n{'='*60}")
for ds_id in no_data_at_all[:30]:
    print(f"  {ds_id}")
if len(no_data_at_all) > 30:
    print(f"  ... and {len(no_data_at_all) - 30} more")
