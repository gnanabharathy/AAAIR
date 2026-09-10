"""
build_shared_variable_lookup.py

Converts one or more variable_collision_pairs-style files (from
find_variable_collisions.py) into a per-dataset lookup: for each
ds_id, which of its OWN variables are shared with some sibling dataset
(same SEQN cycle + same variable name) versus exclusively its own.

Merges ALL matching collision-pairs files found (e.g.
variable_collision_pairs.json for dietary, examination_collision_pairs.json
for examination, etc.) so etl_v3.py's shared-variable protection covers
every category that's been audited, not just the most recently run one.

Output: shared_variables_by_dataset.json
  { "nhanes-dietary-dr1iff_e-2007": ["DR1DAY", "DR1DBIH", ...], ... }

A ds_id not present in this file (or a variable not listed for it) is
assumed fully exclusive -- safe for broad SEQN+variable-name deletion
during ETL reruns.

Usage: python3 build_shared_variable_lookup.py
       python3 build_shared_variable_lookup.py file1.json file2.json ...
"""

import glob
import json
import sys
from collections import defaultdict

if len(sys.argv) > 1:
    input_files = sys.argv[1:]
else:
    input_files = sorted(glob.glob("*collision_pairs.json"))
    if not input_files:
        input_files = ["variable_collision_pairs.json"]

print(f"Merging collision data from: {input_files}")

shared_vars = defaultdict(set)
for path in input_files:
    try:
        pairs = json.load(open(path))
    except FileNotFoundError:
        print(f"  SKIP: {path} not found")
        continue
    for pair in pairs:
        for var in pair["overlap_variables"]:
            shared_vars[pair["ds_id_a"]].add(var)
            shared_vars[pair["ds_id_b"]].add(var)

output = {ds_id: sorted(vars_) for ds_id, vars_ in shared_vars.items()}

with open("shared_variables_by_dataset.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"Built lookup for {len(output)} datasets with at least one shared variable.")
total_shared = sum(len(v) for v in output.values())
print(f"Total (ds_id, shared_variable) pairs: {total_shared}")
