"""
reset_progress_both.py

remove_from_progress.py only clears the "done" list. This also clears
the "failed" list for the given IDs, so stale failures from much
earlier, unrelated runs don't get confused with fresh failures from
the current run.

Usage: python3 reset_progress_both.py <ds_id1> <ds_id2> ...
       python3 reset_progress_both.py --file remaining_19_ids.txt
"""

import json
import sys

if len(sys.argv) < 2:
    print("Usage: python3 reset_progress_both.py <ds_id1> <ds_id2> ...")
    print("       python3 reset_progress_both.py --file <path>")
    sys.exit(1)

if sys.argv[1] == "--file":
    ids_to_reset = set(open(sys.argv[2]).read().splitlines())
else:
    ids_to_reset = set(sys.argv[1:])

progress = json.load(open("batch_progress.json"))

before_done = len(progress["done"])
before_failed = len(progress["failed"])

progress["done"] = [d for d in progress["done"] if d not in ids_to_reset]
progress["failed"] = [d for d in progress["failed"] if d not in ids_to_reset]

json.dump(progress, open("batch_progress.json", "w"), indent=2)

print(f"Removed {before_done - len(progress['done'])} from 'done', "
      f"{before_failed - len(progress['failed'])} from 'failed', "
      f"for {len(ids_to_reset)} requested IDs.")
