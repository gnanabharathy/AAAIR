"""
check_dry_run_capture.py

Minimal diagnostic: runs the SAME reclassification logic as
reclassify_phidu_subtypes.py, but on just 5 specific entries (not all
974), with print() explicitly flushed after every line -- to confirm
output capture works before re-running the full, expensive dry-run.

Usage: python3 check_dry_run_capture.py
"""

import json
import time

from extractor_phidu import llm_classify_subtype

schema = json.load(open("schema.json"))

test_ids = [
    "phidu-pha-aust-aboriginal-males",
    "phidu-pha-aust-migrants-humanitarian",
    "phidu-pha-aust-cmhcs-by-principal-diag",
    "phidu-pha-health-services-ndis-disability",
    "phidu-pha-aust-median-age-death",
]

for ds_id in test_ids:
    entry = schema.get(ds_id)
    if not entry:
        print(f"NOT FOUND: {ds_id}", flush=True)
        continue
    old_subtype = entry.get("subtypes", [None])[0]
    new_subtype = llm_classify_subtype(
        entry.get("sheet", entry.get("name", "")),
        entry.get("desc", ""),
        entry.get("geo", ""),
        entry.get("region", ""),
    )
    print(f"{ds_id}: {old_subtype} -> {new_subtype}", flush=True)
    time.sleep(5)

print("Done.", flush=True)
