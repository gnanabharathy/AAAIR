"""
get_remaining_19.py

Computes the remaining "ok" (real person-centric) dietary datasets
that were NOT in the 82-dataset affected_dataset_ids.txt list --
these are the ones with no known shared-variable collision, but which
should still be re-ETL'd with the dedup-fixed etl_v3.py as a
precaution (the person-constant-field duplication bug is unrelated to
variable sharing between datasets -- it can occur in any dataset
whose raw file structure repeats person-level facts across multiple
rows).

Usage: python3 get_remaining_19.py
"""

import json

classification = json.load(open("backfill_classification.json"))
ok_ids = set(classification["ok"])

affected_ids = set(open("affected_dataset_ids.txt").read().splitlines())

remaining = sorted(ok_ids - affected_ids)

print(f"'ok' (real person-centric) datasets: {len(ok_ids)}")
print(f"Already covered in the 82-dataset rerun: {len(ok_ids & affected_ids)}")
print(f"Remaining, not yet re-verified: {len(remaining)}")
for i in remaining:
    print(" ", i)

with open("remaining_19_ids.txt", "w") as f:
    f.write("\n".join(remaining))
print("\nSaved to remaining_19_ids.txt")
