"""
find_variable_collisions.py

Systematically finds ALL pairs of dietary datasets that could have the
same misattribution problem discovered between dr1iff_e-2007 and
dr1tot_e-2007: sharing both (a) overlapping variable names and (b) an
overlapping SEQN pool (same survey cycle/year).

This doesn't check every pair by brute force -- it groups datasets by
variable name first (fast), then only checks SEQN overlap for pairs
that already share at least one variable name (the expensive check is
reserved for genuine candidates).

Usage: python3 find_variable_collisions.py --category dietary
"""

import argparse
import json
import os
import urllib.request
from collections import defaultdict
from itertools import combinations

import pyreadstat

SEQN_CACHE = {}


def download_xpt_if_needed(ds_id, entry):
    xpt_path = f"/tmp/{ds_id}.xpt"
    if os.path.exists(xpt_path):
        return xpt_path
    doc_url = entry["url"]
    xpt_url = doc_url.replace(".htm", ".xpt").replace(".html", ".xpt")
    req = urllib.request.Request(xpt_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(xpt_path, "wb") as f:
            f.write(r.read())
    return xpt_path


def get_seqns(ds_id, entry):
    if ds_id in SEQN_CACHE:
        return SEQN_CACHE[ds_id]
    try:
        xpt_path = download_xpt_if_needed(ds_id, entry)
        df, _ = pyreadstat.read_xport(xpt_path, encoding="latin1")
        seqns = set(int(s) for s in df["SEQN"].dropna().unique())
    except Exception as e:
        print(f"    WARNING: could not get SEQNs for {ds_id}: {e}")
        seqns = set()
    SEQN_CACHE[ds_id] = seqns
    return seqns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True)
    parser.add_argument("--output", default="variable_collision_pairs.json",
                         help="Output filename (default: variable_collision_pairs.json). "
                              "Use a category-specific name (e.g. "
                              "examination_collision_pairs.json) to avoid overwriting "
                              "a previous category's collision data -- "
                              "build_shared_variable_lookup.py merges multiple such "
                              "files, so keeping them separate per category is safe "
                              "and lets you audit each category's own findings.")
    args = parser.parse_args()

    schema = json.load(open("schema.json"))
    ids = sorted(
        ds_id for ds_id, entry in schema.items()
        if args.category.lower() in [s.lower() for s in entry.get("subtypes", [])]
    )
    print(f"Checking {len(ids)} datasets in category '{args.category}'")

    # Group datasets by variable name (excluding SEQN)
    var_to_datasets = defaultdict(set)
    for ds_id in ids:
        variables = schema[ds_id].get("variables", [])
        for v in variables:
            if v["name"] != "SEQN":
                var_to_datasets[v["name"]].add(ds_id)

    # Find candidate pairs: any two datasets sharing at least one variable name
    candidate_pairs = set()
    for var, ds_set in var_to_datasets.items():
        if len(ds_set) > 1:
            for pair in combinations(sorted(ds_set), 2):
                candidate_pairs.add(pair)

    print(f"\n{len(candidate_pairs)} candidate pairs share at least one variable name.")
    print("Checking SEQN overlap for each candidate pair (this downloads/reads .xpt files)...\n")

    flagged = []
    for ds_id_a, ds_id_b in sorted(candidate_pairs):
        vars_a = {v["name"] for v in schema[ds_id_a].get("variables", [])} - {"SEQN"}
        vars_b = {v["name"] for v in schema[ds_id_b].get("variables", [])} - {"SEQN"}
        overlap_vars = vars_a & vars_b

        seqns_a = get_seqns(ds_id_a, schema[ds_id_a])
        seqns_b = get_seqns(ds_id_b, schema[ds_id_b])
        overlap_seqns = seqns_a & seqns_b

        if overlap_vars and overlap_seqns:
            flagged.append((ds_id_a, ds_id_b, len(overlap_vars), len(overlap_seqns)))
            print(f"FLAGGED: {ds_id_a} <-> {ds_id_b} -- "
                  f"{len(overlap_vars)} shared variables, {len(overlap_seqns)} shared SEQNs "
                  f"-- {sorted(overlap_vars)}")

    print(f"\n{'='*60}")
    print(f"Total flagged pairs needing register_shared_metadata_rows.py: {len(flagged)}")
    print(f"{'='*60}")

    with open(args.output, "w") as f:
        json.dump(
            [{"ds_id_a": a, "ds_id_b": b, "overlap_variables": sorted(
                ({v["name"] for v in schema[a].get("variables", [])} &
                 {v["name"] for v in schema[b].get("variables", [])}) - {"SEQN"}
              ), "overlap_seqn_count": s}
             for a, b, c, s in flagged],
            f, indent=2
        )
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
