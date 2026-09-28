"""
register_vocab_metadata.py

Idempotently ensures the domain_id/vocabulary_id/concept_class_id
values referenced by one or more concept-table specs exist in their
respective OMOP reference tables (domain, vocabulary, concept_class)
before load_concept_data.py tries to insert concept rows that
reference them via foreign key.

Same pattern as the earlier bootstrap_concept.sql approach for
PTB-XL, but generalized to work from spec files instead of being
hand-written per-dataset.

Usage:
    python3 register_vocab_metadata.py <ds_id1> <ds_id2> ...
"""

import json
import sys

import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}


def ensure_domain(cur, domain_id):
    cur.execute("SELECT 1 FROM domain WHERE domain_id = %s", (domain_id,))
    if cur.fetchone():
        return
    cur.execute(
        "INSERT INTO domain (domain_id, domain_name, domain_concept_id) "
        "VALUES (%s, %s, 0)",
        (domain_id, domain_id),
    )
    print(f"  Registered domain: {domain_id}")


def ensure_vocabulary(cur, vocabulary_id):
    cur.execute("SELECT 1 FROM vocabulary WHERE vocabulary_id = %s", (vocabulary_id,))
    if cur.fetchone():
        return
    cur.execute(
        "INSERT INTO vocabulary "
        "(vocabulary_id, vocabulary_name, vocabulary_reference, "
        " vocabulary_version, vocabulary_concept_id) "
        "VALUES (%s, %s, %s, %s, 0)",
        (vocabulary_id, f"{vocabulary_id} (local NHANES vocabulary)",
         "Generated locally from NHANES reference files", "1.0"),
    )
    print(f"  Registered vocabulary: {vocabulary_id}")


def ensure_concept_class(cur, concept_class_id):
    cur.execute("SELECT 1 FROM concept_class WHERE concept_class_id = %s", (concept_class_id,))
    if cur.fetchone():
        return
    cur.execute(
        "INSERT INTO concept_class (concept_class_id, concept_class_name, concept_class_concept_id) "
        "VALUES (%s, %s, 0)",
        (concept_class_id, concept_class_id),
    )
    print(f"  Registered concept_class: {concept_class_id}")


def ensure_english_language_concept(cur):
    """concept_synonym.language_concept_id has a foreign key to
    concept.concept_id -- normally satisfied by loading the full OHDSI
    standard vocabulary (which defines concept_id 4180186 = "English
    language"), but this CDM instance only has a handful of bootstrap
    placeholder rows in concept, not the full vocabulary. Register a
    minimal placeholder so concept_synonym inserts don't fail their FK
    check, consistent with how bootstrap_concept.sql placeholder-ed
    concept_id 0/8507/8532 earlier for the same reason."""
    cur.execute("SELECT 1 FROM concept WHERE concept_id = 4180186")
    if cur.fetchone():
        return
    cur.execute(
        "INSERT INTO concept "
        "(concept_id, concept_name, domain_id, vocabulary_id, "
        " concept_class_id, standard_concept, concept_code, "
        " valid_start_date, valid_end_date, invalid_reason) "
        "VALUES (4180186, 'English language', 'Language', 'None', "
        " 'Undefined', 'S', '4180186', '1970-01-01', '2099-12-31', NULL)"
    )
    print("  Registered placeholder concept 4180186 (English language) "
          "for concept_synonym.language_concept_id FK")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 register_vocab_metadata.py <ds_id1> <ds_id2> ...")
        sys.exit(1)

    ds_ids = sys.argv[1:]
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    ensure_domain(cur, "Language")
    ensure_vocabulary(cur, "None")
    ensure_concept_class(cur, "Undefined")
    ensure_english_language_concept(cur)
    conn.commit()

    seen_domains, seen_vocabs, seen_classes = set(), set(), set()

    for ds_id in ds_ids:
        spec_path = f"dqd/concept_specs/spec_{ds_id}.json"
        try:
            spec = json.load(open(spec_path))
        except FileNotFoundError:
            print(f"SKIP: {spec_path} not found")
            continue

        domain_id = spec.get("domain_id")
        vocabulary_id = spec.get("vocabulary_id")
        concept_class_id = spec.get("concept_class_id")

        if not (domain_id and vocabulary_id and concept_class_id):
            print(f"SKIP: {ds_id} spec is missing domain_id/vocabulary_id/concept_class_id -- review manually.")
            continue

        if domain_id not in seen_domains:
            ensure_domain(cur, domain_id)
            seen_domains.add(domain_id)
        if vocabulary_id not in seen_vocabs:
            ensure_vocabulary(cur, vocabulary_id)
            seen_vocabs.add(vocabulary_id)
        if concept_class_id not in seen_classes:
            ensure_concept_class(cur, concept_class_id)
            seen_classes.add(concept_class_id)

    conn.commit()
    cur.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
