"""
get_affected_dataset_ids.py

Prints the full list of dataset IDs that need to be re-ETL'd with the
dedup-fixed etl_v3.py -- every dataset that appears in
variable_collision_pairs.json (i.e. has at least one variable shared
with a sibling dataset, and is therefore at risk of the person-constant
duplication bug found in dr1iff_e-2007).

Usage: python3 get_affected_dataset_ids.py
"""

import json

pairs = json.load(open("variable_collision_pairs.json"))
ids = set()
for p in pairs:
    ids.add(p["ds_id_a"])
    ids.add(p["ds_id_b"])

ids = sorted(ids)
print(f"{len(ids)} datasets need re-ETL:")
for i in ids:
    print(" ", i)

with open("affected_dataset_ids.txt", "w") as f:
    f.write("\n".join(ids))
print("\nSaved to affected_dataset_ids.txt")
