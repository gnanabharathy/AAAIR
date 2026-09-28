"""
get_examination_collision_ids.py

Extracts the set of examination dataset IDs that appear in
examination_collision_pairs.json -- these are the ones that need a
full re-ETL with the current etl_v3.py (which correctly handles
shared vs. exclusive variables) to fix the misattribution problem
found between spx_e-2007 and enx_e-2007.

Only includes IDs that are also in the "ok" bucket (already have real
data) -- collision partners that are structural/never_etld/network_error
don't need this treatment here.

Usage: python3 get_examination_collision_ids.py
"""

import json

pairs = json.load(open("examination_collision_pairs.json"))
classification = json.load(open("examination_classification.json"))
ok_ids = set(classification["ok"])

collision_ids = set()
for p in pairs:
    collision_ids.add(p["ds_id_a"])
    collision_ids.add(p["ds_id_b"])

# Only the ones that are real "ok" (have data) datasets
affected_ok = sorted(collision_ids & ok_ids)

print(f"Total unique datasets in collision pairs: {len(collision_ids)}")
print(f"Of these, in the 'ok' (real data) bucket: {len(affected_ok)}")
for i in affected_ok:
    print(" ", i)

with open("examination_affected_ids.txt", "w") as f:
    f.write("\n".join(affected_ok))
print("\nSaved to examination_affected_ids.txt")
