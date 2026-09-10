"""
classify_backfill_failures.py

Re-runs backfill_dataset_registry.py's core logic across a category,
but instead of writing anything, just classifies every dataset into
one of four buckets based on what happens:

  - structural_not_applicable: .xpt has no SEQN column at all (e.g.
    dietary supplement reference/lookup tables like DSBI/DSII/DSPI --
    product-level metadata, not person-level records)
  - network_error: download or read failed for a transient-looking
    reason (timeout, incomplete read, connection reset)
  - never_etld: SEQNs and variable names were found fine, but zero
    rows in measurement/observation/person matched -- this dataset was
    likely never actually run through etl_v3.py
  - needs_manual_review: anything else unexpected

This is read-only against schema.json and the CDC .xpt files, but DOES
query (read-only, no writes) the database to check the "never_etld"
case, so it needs the same DB_CONFIG access as backfill itself.

Usage:
    python3 classify_backfill_failures.py --category dietary
    python3 classify_backfill_failures.py --ids ds_id1 ds_id2 ...
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
    entry = schema.get(ds_id)
    if not entry:
        raise ValueError(f"Dataset {ds_id} not found in schema.json")
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


def classify_one(cur, ds_id, schema, use_person_check=False):
    """use_person_check should only be True for the demographics
    category, which is the only one whose datasets actually create
    their OWN rows in the person table. For every other category
    (dietary, examination, laboratory, questionnaire, ...), person_id
    values will ALWAYS appear to "match" because demographics already
    populated the person table for that survey cycle -- that's not
    evidence THIS dataset was ever ETL'd. Using person_matches as a
    positive signal outside demographics produces false "ok"
    classifications for datasets whose own measurement/observation
    contribution is actually zero."""
    entry = schema[ds_id]
    try:
        xpt_path = download_xpt_if_needed(ds_id, schema)
    except Exception as e:
        return "network_error", str(e)

    try:
        df, _ = pyreadstat.read_xport(xpt_path, encoding="latin1")
    except Exception as e:
        return "network_error", f"corrupt/unreadable file: {e}"

    if "SEQN" not in df.columns:
        return "structural_not_applicable", f"no SEQN column -- columns are: {list(df.columns)}"

    seqns = set(int(s) for s in df["SEQN"].dropna().unique())
    var_names = {v["name"] for v in entry.get("variables", [])}

    person_matches = 0
    if use_person_check:
        cur.execute(
            "SELECT COUNT(*) FROM public.person WHERE person_id = ANY(%s)",
            (list(seqns),),
        )
        person_matches = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM public.measurement "
        "WHERE person_id = ANY(%s) AND measurement_source_value = ANY(%s)",
        (list(seqns), list(var_names)),
    )
    measurement_matches = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM public.observation "
        "WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s)",
        (list(seqns), list(var_names)),
    )
    observation_matches = cur.fetchone()[0]

    if person_matches == 0 and measurement_matches == 0 and observation_matches == 0:
        return "never_etld", (
            f"{len(seqns)} SEQNs, {len(var_names)} variable names, "
            f"but zero matching rows in person/measurement/observation"
        )

    return "ok", (
        f"person={person_matches}, measurement={measurement_matches}, "
        f"observation={observation_matches}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--category")
    parser.add_argument("--output", default="backfill_classification.json",
                         help="Output filename (default: backfill_classification.json). "
                              "Use a category-specific name (e.g. "
                              "examination_classification.json) to avoid overwriting "
                              "a previous category's classification results.")
    args = parser.parse_args()

    schema = json.load(open("schema.json"))

    if args.ids:
        ids = args.ids
    elif args.category:
        ids = sorted(
            ds_id for ds_id, entry in schema.items()
            if args.category.lower() in [s.lower() for s in entry.get("subtypes", [])]
        )
    else:
        print("Usage: python3 classify_backfill_failures.py --category dietary")
        return

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    use_person_check = bool(
        args.category and args.category.lower() == "demographics"
    )

    buckets = {
        "ok": [], "structural_not_applicable": [], "network_error": [],
        "never_etld": [], "needs_manual_review": [],
    }

    for ds_id in ids:
        try:
            bucket, detail = classify_one(cur, ds_id, schema, use_person_check=use_person_check)
        except Exception as e:
            bucket, detail = "needs_manual_review", f"unexpected error: {e}"
        buckets[bucket].append((ds_id, detail))
        print(f"[{bucket}] {ds_id}: {detail}")

    cur.close()
    conn.close()

    print(f"\n{'='*60}\nSummary\n{'='*60}")
    for bucket, items in buckets.items():
        print(f"{bucket}: {len(items)}")

    with open(args.output, "w") as f:
        json.dump({k: [ds for ds, _ in v] for k, v in buckets.items()}, f, indent=2)
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
