"""
load_concept_data.py

The generic executor: given a ds_id with an existing spec file
(dqd/concept_specs/spec_{ds_id}.json), reads the actual .xpt data and
mechanically loads it into the OMOP concept/concept_synonym tables per
whatever the spec says -- concept_name_column, concept_code_column,
domain_id, vocabulary_id, concept_class_id, additional_columns_as_synonyms.

This script contains NO per-dataset judgment of its own -- every
decision about what goes where came from the LLM-generated spec. This
is purely a mechanical "read the spec, apply it" interpreter, the same
role _build_measurement_rows/_build_observation_rows play in etl_v2.py
for person-centric datasets.

Handles cross-dataset duplicate concept_codes (e.g. the same USDA food
code recurring across many NHANES survey years in the drxfcd family):
if a (vocabulary_id, concept_code) pair already exists, no new concept
row is inserted, but this ds_id still gets a concept_dataset_registry
entry pointing at the existing concept_id -- a many-to-many attribution
table (see create_concept_dataset_registry.sql), separate from
dataset_row_registry, since multiple datasets legitimately sharing one
concept is a different relationship than dataset_row_registry's
single-owner-per-row semantics used for person/measurement/observation.

Prerequisite: run register_vocab_metadata.py first for the same ds_ids,
so the domain/vocabulary/concept_class rows this spec references
already exist (this script will fail on a foreign key violation
otherwise, which is the correct failure mode -- it should not silently
auto-register metadata behind your back).

Usage:
    python3 load_concept_data.py <ds_id1> <ds_id2> ...
"""

import json
import math
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

LOCAL_CONCEPT_ID_BASE = 2_000_000_000  # OHDSI convention: local/custom
                                       # concepts should not collide
                                       # with real standard vocabulary
                                       # concept_id ranges.


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


def to_str(value):
    """SAS .xpt numeric columns come through as floats even for whole
    numbers (e.g. food code 27210250.0) -- render whole floats without
    the trailing .0, and treat NaN as missing."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return str(int(value))
        return str(value)
    return str(value).strip() or None


def get_next_concept_id(cur, allocated_so_far):
    cur.execute(
        "SELECT COALESCE(MAX(concept_id), %s) FROM public.concept WHERE concept_id >= %s",
        (LOCAL_CONCEPT_ID_BASE - 1, LOCAL_CONCEPT_ID_BASE),
    )
    db_max = cur.fetchone()[0]
    return max(db_max, allocated_so_far) + 1


def load_one(cur, ds_id, schema, next_concept_id_holder):
    spec_path = f"dqd/concept_specs/spec_{ds_id}.json"
    if not os.path.exists(spec_path):
        print(f"SKIP: no spec found for {ds_id} at {spec_path}")
        return 0, 0

    spec = json.load(open(spec_path))

    for key in ("concept_name_column", "concept_code_column", "domain_id",
                "vocabulary_id", "concept_class_id"):
        if not spec.get(key):
            print(f"SKIP: {ds_id} spec is missing required field '{key}'. Review manually.")
            return 0, 0

    if spec.get("one_row_per_concept") is not True:
        print(f"SKIP: {ds_id} spec has one_row_per_concept != true "
              f"(complex relationship, no generic handling implemented yet). "
              f"Notes: {spec.get('notes')}")
        return 0, 0

    entry = schema[ds_id]
    xpt_path = download_xpt_if_needed(ds_id, entry)
    df, _ = pyreadstat.read_xport(xpt_path, encoding="latin1")

    name_col = spec["concept_name_column"]
    code_col = spec["concept_code_column"]
    domain_id = spec["domain_id"]
    vocabulary_id = spec["vocabulary_id"]
    concept_class_id = spec["concept_class_id"]
    synonym_cols = spec.get("additional_columns_as_synonyms", [])

    if name_col not in df.columns or code_col not in df.columns:
        print(f"SKIP: {ds_id} spec references columns not in the actual file "
              f"(name_col={name_col}, code_col={code_col}, real columns={list(df.columns)}).")
        return 0, 0

    print(f"\n{'='*60}\nLoading: {ds_id} ({len(df)} rows)\n{'='*60}")

    inserted, attributed_existing = 0, 0

    for _, row in df.iterrows():
        code = to_str(row[code_col])
        name = to_str(row[name_col])
        if code is None or name is None:
            continue

        cur.execute(
            "SELECT concept_id FROM public.concept "
            "WHERE vocabulary_id = %s AND concept_code = %s",
            (vocabulary_id, code),
        )
        existing = cur.fetchone()

        if existing:
            concept_id = existing[0]
            attributed_existing += 1
        else:
            concept_id = next_concept_id_holder[0]
            next_concept_id_holder[0] += 1

            cur.execute(
                "INSERT INTO public.concept "
                "(concept_id, concept_name, domain_id, vocabulary_id, "
                " concept_class_id, standard_concept, concept_code, "
                " valid_start_date, valid_end_date, invalid_reason) "
                "VALUES (%s, %s, %s, %s, %s, NULL, %s, '1970-01-01', '2099-12-31', NULL)",
                (concept_id, name[:255], domain_id, vocabulary_id,
                 concept_class_id, code),
            )
            inserted += 1

            for syn_col in synonym_cols:
                if syn_col not in df.columns:
                    continue
                syn_value = to_str(row[syn_col])
                if syn_value is None:
                    continue
                cur.execute(
                    "INSERT INTO public.concept_synonym "
                    "(concept_id, concept_synonym_name, language_concept_id) "
                    "VALUES (%s, %s, 4180186)",  # 4180186 = English
                    (concept_id, syn_value[:1000]),
                )

        cur.execute(
            "INSERT INTO public.concept_dataset_registry (ds_id, concept_id) "
            "VALUES (%s, %s) "
            "ON CONFLICT (ds_id, concept_id) DO NOTHING",
            (ds_id, concept_id),
        )

    print(f"  {inserted} new concepts inserted, {attributed_existing} rows "
          f"attributed to already-existing concepts.")
    return inserted, attributed_existing


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 load_concept_data.py <ds_id1> <ds_id2> ...")
        sys.exit(1)

    ds_ids = sys.argv[1:]
    schema = json.load(open("schema.json"))

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    next_concept_id_holder = [get_next_concept_id(cur, 0)]

    total_inserted, total_attributed = 0, 0
    for ds_id in ds_ids:
        try:
            inserted, attributed = load_one(cur, ds_id, schema, next_concept_id_holder)
            total_inserted += inserted
            total_attributed += attributed
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"  FAILED for {ds_id}: {e}")
            # re-sync the concept_id counter with the DB in case this
            # dataset's failed transaction affected what's actually committed
            next_concept_id_holder[0] = get_next_concept_id(cur, 0)

    cur.close()
    conn.close()

    print(f"\n{'='*60}\nDone. Total new concepts: {total_inserted}. "
          f"Total rows attributed to existing concepts: {total_attributed}.\n{'='*60}")


if __name__ == "__main__":
    main()
