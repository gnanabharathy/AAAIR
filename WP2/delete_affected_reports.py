"""
delete_affected_reports.py

Deletes existing dqd/raw/{ds_id}.json reports for every dataset in
affected_dataset_ids.txt, so that re-running batch_etl_dqd_new.py
(after the ETL dedup fix) actually regenerates their DQD reports
instead of skipping because a (now-stale) report already exists.

Usage: python3 delete_affected_reports.py
"""

import os

ids = open("remaining_19_ids.txt").read().splitlines()

deleted = 0
for ds_id in ids:
    path = f"dqd/raw/{ds_id}.json"
    if os.path.exists(path):
        os.remove(path)
        deleted += 1

print(f"Deleted {deleted} of {len(ids)} existing reports.")
