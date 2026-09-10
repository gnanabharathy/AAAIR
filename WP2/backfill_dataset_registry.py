"""
backfill_dataset_registry.py

Retroactively populates dataset_row_registry for datasets that were
ETL'd BEFORE the registry existed (e.g. all 12 demographics datasets).
Does NOT touch or reinsert any actual data -- purely attributes
existing rows.

Why not just match by variable name (measurement_source_value /
observation_source_value)? Because demographics datasets across
different NHANES cycles reuse the same variable names (e.g. RIAGENDR
appears in every cycle's demographics file), so variable name alone
can't disambiguate WHICH cycle a row belongs to.

The fix: each NHANES cycle samples a distinct, non-overlapping set of
respondents (SEQN). So:
  1. Re-download each dataset's .xpt (reusing the cached /tmp/{ds_id}.xpt
     if present) and extract its actual SEQN set.
  2. Attribute PERSON rows by direct SEQN membership -- unambiguous,
     no variable-name matching needed.
  3. Attribute MEASUREMENT/OBSERVATION rows by BOTH conditions at once:
     the row's person_id is in this dataset's SEQN set, AND its
     source_value matches a variable name in this dataset's schema.json
     variables list. Requiring both avoids misattribution even when
     variable names collide across cycles.

Usage:
    python3 backfill_dataset_registry.py --ids ds_id1 ds_id2 ...
    python3 backfill_dataset_registry.py --category demographics
"""

import argparse
import json
import os
import urllib.request

import pandas as pd
import psycopg2
import pyreadstat

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}


def download_xpt_if_needed(ds_id, schema):
    """Reuses the same caching convention as etl_v2.py's download_xpt."""
    entry = schema.get(ds_id)
    if not entry:
        raise ValueError(f"Dataset {ds_id} not found in schema.json")

    xpt_path = f"/tmp/{ds_id}.xpt"
    if os.path.exists(xpt_path):
        print(f"  .xpt already cached: {xpt_path}")
        return xpt_path

    doc_url = entry["url"]
    xpt_url = doc_url.replace(".htm", ".xpt").replace(".html", ".xpt")
    print(f"  Downloading {xpt_url}...")
    req = urllib.request.Request(xpt_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(xpt_path, "wb") as f:
            f.write(r.read())
    return xpt_path


def get_seqns(xpt_path):
    df, _ = pyreadstat.read_xport(xpt_path, encoding="latin1")
    return set(int(s) for s in df["SEQN"].dropna().unique())


def get_dataset_variable_names(schema_entry):
    return {v["name"] for v in schema_entry.get("variables", [])}


def already_backfilled(cur, ds_id):
    """Skip datasets that already have registry entries -- avoids
    re-downloading and re-processing datasets that succeeded in a
    previous run (e.g. before a crash interrupted the batch partway
    through). ON CONFLICT DO NOTHING would make re-running safe anyway,
    but this avoids the wasted time of redoing already-finished work."""
    cur.execute(
        "SELECT EXISTS(SELECT 1 FROM dataset_row_registry WHERE ds_id = %s)",
        (ds_id,),
    )
    return cur.fetchone()[0]


def backfill_one(cur, ds_id, schema):
    print(f"\n{'='*60}\nBackfilling: {ds_id}\n{'='*60}")

    entry = schema[ds_id]
    xpt_path = download_xpt_if_needed(ds_id, schema)
    seqns = get_seqns(xpt_path)
    var_names = get_dataset_variable_names(entry)
    print(f"  {len(seqns)} SEQNs, {len(var_names)} variable names in schema.json")

    # --- person ---
    cur.execute(
        """
        INSERT INTO dataset_row_registry (ds_id, table_name, row_id)
        SELECT %s, 'person', person_id FROM public.person
        WHERE person_id = ANY(%s)
        ON CONFLICT (table_name, row_id) DO NOTHING
        """,
        (ds_id, list(seqns)),
    )
    person_attributed = cur.rowcount
    print(f"  person: {person_attributed} rows attributed")

    # --- measurement: person_id in this dataset's SEQNs AND source_value
    #     matches one of this dataset's variable names ---
    cur.execute(
        """
        INSERT INTO dataset_row_registry (ds_id, table_name, row_id)
        SELECT %s, 'measurement', measurement_id FROM public.measurement
        WHERE person_id = ANY(%s) AND measurement_source_value = ANY(%s)
        ON CONFLICT (table_name, row_id) DO NOTHING
        """,
        (ds_id, list(seqns), list(var_names)),
    )
    measurement_attributed = cur.rowcount
    print(f"  measurement: {measurement_attributed} rows attributed")

    # --- observation: same dual condition ---
    cur.execute(
        """
        INSERT INTO dataset_row_registry (ds_id, table_name, row_id)
        SELECT %s, 'observation', observation_id FROM public.observation
        WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s)
        ON CONFLICT (table_name, row_id) DO NOTHING
        """,
        (ds_id, list(seqns), list(var_names)),
    )
    observation_attributed = cur.rowcount
    print(f"  observation: {observation_attributed} rows attributed")

    return person_attributed, measurement_attributed, observation_attributed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", help="Specific dataset IDs to backfill")
    parser.add_argument("--category", help="Category to backfill (e.g. demographics)")
    args = parser.parse_args()

    schema = json.load(open("schema.json"))

    if args.ids:
        ids = args.ids
    elif args.category:
        ids = sorted(
            ds_id for ds_id, entry in schema.items()
            if args.category.lower() in [s.lower() for s in entry.get("subtypes", [])]
        )
        print(f"Found {len(ids)} datasets in category '{args.category}': {ids}")
    else:
        print("Usage: python3 backfill_dataset_registry.py --ids <id1> <id2> ...")
        print("       python3 backfill_dataset_registry.py --category demographics")
        return

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    totals = {"person": 0, "measurement": 0, "observation": 0}
    skipped = 0
    for ds_id in ids:
        try:
            if already_backfilled(cur, ds_id):
                print(f"[SKIP] Already backfilled: {ds_id}")
                skipped += 1
                continue
            p, m, o = backfill_one(cur, ds_id, schema)
            totals["person"] += p
            totals["measurement"] += m
            totals["observation"] += o
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"  FAILED for {ds_id}: {e}")

    cur.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Backfill complete. Skipped (already done): {skipped}. Totals attributed: {totals}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
