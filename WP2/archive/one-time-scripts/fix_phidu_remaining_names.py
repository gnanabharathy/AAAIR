"""
fix_phidu_remaining_names.py

Fixes the 2 PHIDU entries whose 'name' field is still the raw,
unprocessed sheet name (never went through real LLM naming, since
their original LLM call failed and the fallback default was used --
the same entries whose 'desc' was already fixed in
fix_phidu_desc_issues.py, but that fix only touched desc, not name).

Usage: python3 fix_phidu_remaining_names.py
"""

import json
import shutil
from datetime import datetime

SCHEMA_FILE = "schema.json"
d = json.load(open(SCHEMA_FILE))

changes = {
    "phidu-pha-qld-migrants-humanitarian": {
        "name": "Humanitarian Program Migrants by PHA (Qld)",
    },
    "phidu-pha-tas-migrants-total": {
        "name": "Total Migrant Arrivals by PHA (Tas)",
    },
}

print(f"Applying {len(changes)} name fixes...\n")
for ds_id, updates in changes.items():
    entry = d.get(ds_id)
    if entry is None:
        print(f"  WARNING: {ds_id} not found -- skipped")
        continue
    for field, new_value in updates.items():
        old_value = entry.get(field)
        entry[field] = new_value
        print(f"  {ds_id}.{field}: '{old_value}' -> '{new_value}'")

backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy(SCHEMA_FILE, backup_name)
print(f"\nBacked up existing schema.json to {backup_name}")

with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)

print("Wrote schema.json.")
