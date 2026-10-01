"""
fix_phidu_desc_issues.py

Fixes two confirmed, specific PHIDU data-quality issues:

1. chsp subtype inconsistency: phidu-pha-vic-chsp was classified as
   'social-determinants' while every other region's chsp entry (9 of
   10) was correctly classified as 'health-services' (Commonwealth
   Home Support Programme -- a service-utilisation program, not a
   social determinant). This is a one-off LLM inconsistency, not a
   genuine ambiguous case -- corrected directly, no LLM call needed.

2. Duplicate/inaccurate descriptions:
   - phidu-pha-qld-migrants-humanitarian and phidu-pha-tas-migrants-total
     still carry the old generic fallback description ("PHIDU PHA by
     location data for Population Health Area") from when their LLM
     call originally failed -- given real, sheet-specific descriptions.
   - phidu-pha-sa-median-age-death, phidu-pha-sa-years-life-lost-by-cause,
     and phidu-pha-sa-ndis-disability had descriptions that were
     word-for-word identical to their Australia-wide "PHA by topic"
     counterparts, wrongly implying national coverage for data that is
     actually South-Australia-specific -- reworded to explicitly say
     "in South Australia".

Usage: python3 fix_phidu_desc_issues.py
"""

import json
import shutil
from datetime import datetime

SCHEMA_FILE = "schema.json"
d = json.load(open(SCHEMA_FILE))

changes = {
    "phidu-pha-vic-chsp": {
        "subtypes": ["health-services"],
    },
    "phidu-pha-qld-migrants-humanitarian": {
        "desc": "Counts of humanitarian program migrant arrivals by Population Health Area in Queensland.",
    },
    "phidu-pha-tas-migrants-total": {
        "desc": "Total counts of migrant arrivals by Population Health Area in Tasmania.",
    },
    "phidu-pha-sa-median-age-death": {
        "desc": "Dataset of median age at death for males, females, and all persons by Population Health Area in South Australia.",
    },
    "phidu-pha-sa-years-life-lost-by-cause": {
        "desc": "Dataset of potential years of life lost before age 75 for various causes by Population Health Area in South Australia.",
    },
    "phidu-pha-sa-ndis-disability": {
        "desc": "Counts of National Disability Insurance Scheme participants across nine age brackets by Population Health Area in South Australia.",
    },
}

print(f"Applying {len(changes)} targeted fixes...\n")

applied = 0
for ds_id, updates in changes.items():
    entry = d.get(ds_id)
    if entry is None:
        print(f"  WARNING: {ds_id} not found in schema.json -- skipped")
        continue
    for field, new_value in updates.items():
        old_value = entry.get(field)
        entry[field] = new_value
        print(f"  {ds_id}.{field}:")
        print(f"    old: {old_value}")
        print(f"    new: {new_value}")
    applied += 1

backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy(SCHEMA_FILE, backup_name)
print(f"\nBacked up existing schema.json to {backup_name}")

with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)

print(f"Wrote schema.json with {applied} entries fixed.")
