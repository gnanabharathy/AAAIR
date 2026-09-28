"""
check_observation_denominator.py

explore_dqd_rowcounts.py only checked PERSON and MEASUREMENT tables.
This checks the OBSERVATION table's denominator specifically -- the
part that was affected by demo-1999's registry bug and just got fixed.

Usage: python3 check_observation_denominator.py <path/to/report.json>
"""

import json
import sys

path = sys.argv[1]
data = json.load(open(path))
results = data.get("CheckResults", [])

print(f"File: {path}\n")
seen = set()
for r in results:
    if r.get("cdmTableName") == "OBSERVATION":
        key = (r.get("checkName"), r.get("numDenominatorRows"))
        if key not in seen:
            seen.add(key)
            print(f"checkName={r.get('checkName'):<30} numDenominatorRows={r.get('numDenominatorRows')}")
