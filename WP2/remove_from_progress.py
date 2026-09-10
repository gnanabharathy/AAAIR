"""
remove_from_progress.py

Removes the given dataset IDs from batch_progress.json's "done" list,
so batch_etl_dqd_new.py will actually reprocess them instead of
silently skipping with "[SKIP] Already done".

Usage:
    python3 remove_from_progress.py ds_id1 ds_id2 ...
    python3 remove_from_progress.py --category dietary
"""

import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("ids", nargs="*", help="Specific dataset IDs to remove")
parser.add_argument("--category", help="Remove all datasets in this category (e.g. dietary)")
args = parser.parse_args()

if args.category:
    schema = json.load(open("schema.json"))
    ids_to_remove = set(
        ds_id for ds_id, entry in schema.items()
        if args.category.lower() in [s.lower() for s in entry.get("subtypes", [])]
    )
    print(f"Found {len(ids_to_remove)} datasets in category '{args.category}'")
elif args.ids:
    ids_to_remove = set(args.ids)
else:
    print("Usage: python3 remove_from_progress.py <ds_id1> <ds_id2> ...")
    print("       python3 remove_from_progress.py --category dietary")
    raise SystemExit(1)

progress = json.load(open("batch_progress.json"))
before = len(progress["done"])
progress["done"] = [d for d in progress["done"] if d not in ids_to_remove]
after = len(progress["done"])

json.dump(progress, open("batch_progress.json", "w"), indent=2)

removed = before - after
print(f"Removed {removed} of {len(ids_to_remove)} requested IDs from 'done' list.")
print(f"batch_progress.json updated.")
