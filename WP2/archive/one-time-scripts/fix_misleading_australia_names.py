"""
fix_misleading_australia_names.py

Fixes 8 PHIDU entries whose name says "Australian"/"Australia" in a
way that implies national coverage, when the entry's actual region is
a specific state (SA or ACT) -- and the name does NOT also mention
that state anywhere, so a reader has no way to tell from the title
alone that this is state-specific, not national, data.

This is a small, hand-reviewed list (not a general regex rule) because
telling "Australian" used misleadingly (implying scope) apart from
"Australian" used legitimately (e.g. "Australian Census" referring to
the ABS Census as a proper noun/data source, not this extract's
geographic scope) needs actual judgment, not a pattern match. The 7
other SA/ACT entries found alongside these that ALSO mention
"Australian" but already separately mention SA/ACT somewhere in the
title (e.g. "Australian Skilled Migrant Arrivals by SA") were reviewed
and left alone -- they're not actually misleading, since the state is
already named.

Usage: python3 fix_misleading_australia_names.py
"""

import json
import shutil
from datetime import datetime

SCHEMA_FILE = "schema.json"
d = json.load(open(SCHEMA_FILE))

changes = {
    "phidu-pha-sa-pop-projections-persons": {
        "name": "Population Projections by Age Group for South Australian Population Health Areas",
    },
    "phidu-pha-sa-labour-force": {
        "name": "South Australian Labour Force by Population Health Area",
    },
    "phidu-pha-sa-screening-age": {
        "name": "South Australian Screening Ages by Birth Origin and Residency",
    },
    "phidu-pha-sa-years-life-lost-persons-age": {
        "name": "Potential Years of Life Lost by Age Group in South Australian Population Health Areas",
    },
    "phidu-pha-sa-hosp-type-sex": {
        "name": "Hospital Admissions by Sex and Type in South Australian Population Health Areas",
    },
    "phidu-pha-act-birthplace-nes-residents": {
        "name": "Birthplace NES Residents by PHA (ACT)",
    },
    "phidu-pha-act-estimates-mental-health-males": {
        "name": "Estimated Mental Health Disorder Counts for Males in ACT PHAs",
    },
    "phidu-pha-act-estimates-mental-health-females": {
        "name": "Estimated Mental Health Disorder Counts for Females in ACT PHAs",
    },
}

print(f"Applying {len(changes)} name corrections...\n")
for ds_id, updates in changes.items():
    entry = d.get(ds_id)
    if entry is None:
        print(f"  WARNING: {ds_id} not found -- skipped")
        continue
    for field, new_value in updates.items():
        old_value = entry.get(field)
        entry[field] = new_value
        print(f"  {ds_id}:")
        print(f"    old: {old_value}")
        print(f"    new: {new_value}")

backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy(SCHEMA_FILE, backup_name)
print(f"\nBacked up existing schema.json to {backup_name}")

with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)

print("Wrote schema.json.")
