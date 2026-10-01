import json
import shutil
from datetime import datetime

SCHEMA_FILE = "schema.json"

d = json.load(open(SCHEMA_FILE))

to_remove = [
    k for k, v in d.items()
    if v.get('source') == 'PHIDU'
    and v.get('variable_count', -1) == 0
    and v.get('sheet', '').lower().replace(' ', '_') in ('phas', 'notes_on_the_data')
]

print(f"Found {len(to_remove)} entries to remove:")
for k in to_remove:
    print(f"  {k} (sheet={d[k].get('sheet')})")

if not to_remove:
    print("Nothing to remove.")
else:
    backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy(SCHEMA_FILE, backup_name)
    print(f"\nBacked up existing schema.json to {backup_name}")

    for k in to_remove:
        del d[k]

    with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

    print(f"Removed {len(to_remove)} entries. schema.json now has {len(d)} entries.")
