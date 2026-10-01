"""
apply_dryrun_results.py

Applies the subtype changes from a saved reclassify_phidu_subtypes.py
--dry-run log directly to schema.json, WITHOUT calling the LLM again.
The dry run already computed and printed every single decision --
there's no need to spend another hour and another 974 API calls
re-deriving the exact same answers.

Parses lines matching:
    [N/974] CHANGED: <ds_id> :: <old_subtype> -> <new_subtype>
and ignores "OK (unchanged)" lines (nothing to do for those) and any
interleaved "NIM attempt ... failed" retry-noise lines.

Usage: python3 apply_dryrun_results.py dryrun_log.txt
"""

import json
import re
import shutil
import sys
from datetime import datetime

if len(sys.argv) < 2:
    print("Usage: python3 apply_dryrun_results.py <path_to_dryrun_log.txt>")
    sys.exit(1)

log_path = sys.argv[1]
log_text = open(log_path, encoding="utf-8").read()

pattern = re.compile(
    r"CHANGED:\s+(\S+)\s+::\s+(\S+)\s+->\s+(\S+)"
)
matches = pattern.findall(log_text)
print(f"Parsed {len(matches)} CHANGED lines from {log_path}")

schema = json.load(open("schema.json"))

applied = 0
skipped_not_found = 0
skipped_already_matches = 0
skipped_old_mismatch = []

for ds_id, old_subtype, new_subtype in matches:
    entry = schema.get(ds_id)
    if entry is None:
        skipped_not_found += 1
        continue

    current = entry.get("subtypes", [None])[0]

    if current == new_subtype:
        skipped_already_matches += 1
        continue

    if current != old_subtype:
        # schema.json has moved on since the log was generated (e.g. this
        # entry was edited some other way in between) -- don't blindly
        # overwrite; flag it for a human look instead of guessing.
        skipped_old_mismatch.append((ds_id, old_subtype, current, new_subtype))
        continue

    entry["subtypes"] = [new_subtype]
    applied += 1

print(f"\nApplied: {applied}")
print(f"Already matched target (no-op): {skipped_already_matches}")
print(f"Not found in schema.json: {skipped_not_found}")
print(f"Skipped -- schema.json's current value didn't match the log's "
      f"expected 'old' value: {len(skipped_old_mismatch)}")
for ds_id, expected_old, actual, new in skipped_old_mismatch[:10]:
    print(f"  {ds_id}: log expected old='{expected_old}', "
          f"schema.json actually has '{actual}' (target was '{new}')")

if applied == 0:
    print("\nNothing to apply -- schema.json not modified.")
else:
    backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy("schema.json", backup_name)
    print(f"\nBacked up existing schema.json to {backup_name}")

    with open("schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"Wrote schema.json with {applied} subtype updates applied.")
