"""
inspect_xpt_columns.py

Quick one-off: print the actual column names in a cached .xpt file,
for datasets where backfill_dataset_registry.py failed with a 'SEQN'
KeyError (meaning the file uses a different respondent-ID column name
than expected).

Usage: python3 inspect_xpt_columns.py <ds_id>
"""

import sys
import pyreadstat

ds_id = sys.argv[1]
xpt_path = f"/tmp/{ds_id}.xpt"

df, meta = pyreadstat.read_xport(xpt_path, encoding="latin1", metadataonly=True)
print(f"File: {xpt_path}")
print(f"Columns ({len(df.columns)}):")
for col in df.columns:
    print(f"  {col}")
