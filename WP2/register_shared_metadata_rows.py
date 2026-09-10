"""
register_shared_metadata_rows.py

For a pair of datasets that share the same SEQN pool AND some
identical metadata variable names (e.g. DR1IFF/DR1TOT both containing
DRDINT/WTDRD1/DR1LANG etc.), this:

  1. Finds the overlapping variable names between the two datasets'
     schema.json variable lists.
  2. Finds the observation rows matching those overlapping variables
     (for this pair's shared SEQN pool).
  3. Registers those rows in shared_row_registry under BOTH ds_ids
     (does NOT touch dataset_row_registry -- ownership for safe-DELETE
     purposes stays with whichever one already has it, if any).
  4. Separately backfills dataset_row_registry for each dataset's
     EXCLUSIVE (non-overlapping) variables, if not already done.

Use this when two datasets have ALREADY been ETL'd (their rows exist
in measurement/observation) and only need their shared-variable rows
correctly cross-registered -- it does not touch or re-insert any data.
For a dataset that needs its person-constant-field duplication fixed
at the source, re-run etl_v3.py instead (it handles this
automatically using shared_variables_by_dataset.json).

Usage:
    python3 register_shared_metadata_rows.py <ds_id_a> <ds_id_b>
"""

import json
import os
import sys
import urllib.request

import psycopg2
import pyreadstat

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}


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
    xpt_path = download_xpt_if_needed(ds_id, entry)
    df, _ = pyreadstat.read_xport(xpt_path, encoding="latin1")
    return set(int(s) for s in df["SEQN"].dropna().unique())


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 register_shared_metadata_rows.py <ds_id_a> <ds_id_b>")
        sys.exit(1)

    ds_id_a, ds_id_b = sys.argv[1], sys.argv[2]
    schema = json.load(open("schema.json"))
    entry_a, entry_b = schema[ds_id_a], schema[ds_id_b]

    vars_a = {v["name"] for v in entry_a.get("variables", [])}
    vars_b = {v["name"] for v in entry_b.get("variables", [])}
    overlap = (vars_a & vars_b) - {"SEQN"}
    only_a = vars_a - vars_b - {"SEQN"}
    only_b = vars_b - vars_a - {"SEQN"}

    print(f"Overlapping variables: {sorted(overlap)}")
    print(f"{ds_id_a}-only variables: {len(only_a)}")
    print(f"{ds_id_b}-only variables: {len(only_b)}")

    seqns_a = get_seqns(ds_id_a, entry_a)
    seqns_b = get_seqns(ds_id_b, entry_b)
    shared_seqns = seqns_a & seqns_b
    print(f"Shared SEQN pool: {len(shared_seqns)}")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    # Step 1: register overlapping-variable rows as SHARED (both ds_ids)
    if overlap:
        for ds_id in (ds_id_a, ds_id_b):
            cur.execute(
                "INSERT INTO shared_row_registry (ds_id, table_name, row_id) "
                "SELECT %s, 'observation', observation_id FROM public.observation "
                "WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s) "
                "ON CONFLICT (ds_id, table_name, row_id) DO NOTHING",
                (ds_id, list(shared_seqns), list(overlap)),
            )
            print(f"  Registered {cur.rowcount} shared rows for {ds_id}")

    # Step 2: backfill dataset_row_registry for each dataset's EXCLUSIVE variables
    for ds_id, exclusive_vars, seqns in (
        (ds_id_a, only_a, seqns_a), (ds_id_b, only_b, seqns_b)
    ):
        if not exclusive_vars:
            continue
        cur.execute(
            "INSERT INTO dataset_row_registry (ds_id, table_name, row_id) "
            "SELECT %s, 'observation', observation_id FROM public.observation "
            "WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s) "
            "ON CONFLICT (table_name, row_id) DO NOTHING",
            (ds_id, list(seqns), list(exclusive_vars)),
        )
        print(f"  Registered {cur.rowcount} exclusive-owned rows for {ds_id}")

        cur.execute(
            "INSERT INTO dataset_row_registry (ds_id, table_name, row_id) "
            "SELECT %s, 'measurement', measurement_id FROM public.measurement "
            "WHERE person_id = ANY(%s) AND measurement_source_value = ANY(%s) "
            "ON CONFLICT (table_name, row_id) DO NOTHING",
            (ds_id, list(seqns), list(exclusive_vars)),
        )
        print(f"  Registered {cur.rowcount} exclusive-owned measurement rows for {ds_id}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
