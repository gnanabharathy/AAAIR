"""
final_verify_phidu.py

Final sweep: confirms zero truncated descriptions remain across all
PHIDU entries after the fix_truncated_phidu_desc.py /
fix_last_2_truncated.py / fix_final_one.py rounds.

Usage: python3 final_verify_phidu.py
"""

import json
import re

d = json.load(open("schema.json"))
phidu = {k: v for k, v in d.items() if v.get("source") == "PHIDU"}

def is_truncated(desc):
    desc = desc.strip()
    return (not desc) or (not re.search(r'[.!?]\s*$', desc))

still_truncated = [k for k, v in phidu.items() if is_truncated(v.get("desc", ""))]

print(f"Checked {len(phidu)} PHIDU entries.")
print(f"Still truncated: {len(still_truncated)}")
for k in still_truncated:
    print(f"  {k}: {phidu[k].get('desc')!r}")

if not still_truncated:
    print("\nAll clear -- no truncated descriptions remain.")
