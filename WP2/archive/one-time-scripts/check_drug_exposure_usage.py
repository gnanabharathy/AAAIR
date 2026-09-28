"""
check_drug_exposure_usage.py

Checks how many datasets across schema.json have at least one variable
whose CACHED mapping suggests omop_table='DRUG_EXPOSURE' -- this tells
us whether extending etl_v3.py to support this table would only help
one dataset (dsqfile1-1999) or several, which changes whether it's
worth the investment now.

Usage: python3 check_drug_exposure_usage.py
"""

import glob
import json

affected = {}

for path in glob.glob("dqd/mapping/mapping_*.json"):
    ds_id = path.replace("dqd/mapping/mapping_", "").replace(".json", "")
    try:
        mapping = json.load(open(path))
    except Exception:
        continue
    if not isinstance(mapping, list):
        continue
    drug_exp_vars = [m.get("nhanes_var") for m in mapping if m.get("omop_table") == "DRUG_EXPOSURE"]
    if drug_exp_vars:
        affected[ds_id] = drug_exp_vars

print(f"{len(affected)} datasets have at least one variable mapped to DRUG_EXPOSURE:\n")
for ds_id, vars_ in affected.items():
    print(f"  {ds_id}: {vars_}")
