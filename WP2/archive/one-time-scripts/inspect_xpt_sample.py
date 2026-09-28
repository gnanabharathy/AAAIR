"""
inspect_xpt_sample.py

Prints column names AND a few sample rows of a cached .xpt file, so we
can see actual data (not just column names) when a generated concept
spec looks suspicious (e.g. references a column that doesn't exist).

Usage: python3 inspect_xpt_sample.py <ds_id>
"""

import sys
import pyreadstat

ds_id = sys.argv[1]
xpt_path = f"/tmp/{ds_id}.xpt"

df, meta = pyreadstat.read_xport(xpt_path, encoding="latin1")
print(f"File: {xpt_path}")
print(f"Columns: {list(df.columns)}")
print(f"Column labels: {meta.column_names_to_labels}")
print(f"\n{len(df)} rows total. First 10 rows:\n")
print(df.head(10).to_string())
