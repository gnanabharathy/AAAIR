"""
explore_dqd_rowcounts.py

Prints every (checkName, cdmTableName, numDenominatorRows) combination
for the PERSON and MEASUREMENT tables in ONE report file, so we can see
which checkName's numDenominatorRows actually reflects real row counts
(as opposed to 0, 1, or some other non-row-count denominator).

Usage: python3 explore_dqd_rowcounts.py [path/to/report.json]
"""

import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "dqd/raw/nhanes-demographics-demo-1999.json"
data = json.load(open(path))
results = data.get("CheckResults", [])

print(f"File: {path}\n")
seen = set()
for r in results:
    table = r.get("cdmTableName", "")
    if table in ("PERSON", "MEASUREMENT"):
        key = (r.get("checkName"), table, r.get("numDenominatorRows"))
        if key not in seen:
            seen.add(key)
            print(f"checkName={r.get('checkName'):<30} table={table:<12} "
                  f"numDenominatorRows={r.get('numDenominatorRows')}")
