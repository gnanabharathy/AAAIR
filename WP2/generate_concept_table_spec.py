"""
generate_concept_table_spec.py

For reference/lookup datasets that the LLM has already determined map
to the OMOP "concept" table (see generate_mapping_for_reference_tables.py),
this asks the LLM a dataset-level (not per-variable) question: given
the full column structure of one row, how should ONE ROW of this file
be transformed into one or more concept table records?

The LLM's answer specifies field ROLES (which column plays
concept_name, concept_code, etc.) and suggested domain_id/vocabulary_id/
concept_class_id values. A single GENERIC Python function (see
build_concept_rows_from_spec below) then mechanically executes
whatever role-mapping the LLM specified -- it contains no dataset-
specific judgment of its own, only generic "read the spec, apply it"
logic, the same pattern already used for measurement/observation.

This script only generates and prints/saves the LLM's spec -- it does
not insert anything into the database.

Usage:
    python3 generate_concept_table_spec.py <ds_id1> <ds_id2> ...
"""

import json
import os
import re
import sys
import time
import urllib.request

import pyreadstat

for line in open(".env").read().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

NIM_API_KEY = os.getenv("NIM_API_KEY", "")
NIM_MODEL = os.getenv("NIM_MODEL")
NIM_BASE_URL = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

SYSTEM_CONCEPT_SPEC = """You are an OMOP CDM 5.3 vocabulary expert.
Your job is to specify how ONE ROW of a reference/lookup data file
should be transformed into one or more rows in the OMOP CDM "concept"
table. You decide field roles and vocabulary metadata -- you do not
write code, only specify the mapping precisely enough that a generic
program can mechanically apply it.
Return ONLY valid JSON, no markdown fences, no explanation."""

def get_sample_rows(ds_id, entry, n=5):
    """Read a few real data rows (not just column metadata) so the
    LLM can verify what's actually IN each column, rather than
    guessing from column names/labels alone -- this is what caught
    the reversed concept_name/concept_code columns in varlk_c-2003."""
    xpt_path = download_xpt_if_needed(ds_id, entry)
    df, _ = pyreadstat.read_xport(xpt_path, encoding="latin1")
    return df.head(n).to_dict(orient="records")


PROMPT_TEMPLATE = """This NHANES reference/lookup file has the following columns:
{columns}

Sample of variable descriptions (from schema.json):
{variables}

Here are {n_samples} real sample rows from the actual file, so you can
verify what kind of data is really in each column rather than guessing
from column names alone:
{sample_rows}

Specify how each row of this file becomes one or more OMOP "concept"
table rows. Return ONLY a JSON object with these exact keys:
  "concept_name_column"   - which column's value becomes concept_name (must be a column name from the list above)
  "concept_code_column"   - which column's value becomes concept_code (must be a column name from the list above; should be a unique identifier)
  "domain_id"              - suggested domain_id string for these concepts
  "vocabulary_id"          - suggested vocabulary_id string (a new local vocabulary name specific to this NHANES file, e.g. "NHANES_DSBI")
  "concept_class_id"       - suggested concept_class_id string
  "one_row_per_concept"    - true if each row of the file becomes exactly one concept row, false if the relationship is more complex (explain in notes if false)
  "additional_columns_as_synonyms" - list of other column names (if any) whose values should be stored as concept synonyms rather than discarded
  "notes"                  - explanation of your choices, and any caveats (e.g. if this file actually represents a relationship between two concepts rather than a single concept)
"""


def nim_chat(messages, max_tokens=6144, retries=3):
    payload = json.dumps({
        "model": NIM_MODEL, "messages": messages,
        "max_tokens": max_tokens, "temperature": 0.0,
    }).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{NIM_BASE_URL}/chat/completions", data=payload,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {NIM_API_KEY}"},
                method="POST")
            with urllib.request.urlopen(req, timeout=180) as r:
                msg = json.loads(r.read())["choices"][0]["message"]
                return msg.get("content") or msg.get("reasoning_content") or ""
        except Exception as e:
            print(f"  NIM attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(60)
    raise RuntimeError("NIM API failed after retries")


def safe_json(text, default):
    text = re.sub(r'^```[a-z]*\n?', '', text.strip(), flags=re.I)
    text = re.sub(r'\n?```$', '', text.strip())
    try:
        return json.loads(text)
    except Exception:
        i = text.find('{')
        if i != -1:
            try:
                return json.loads(text[i:])
            except Exception:
                pass
    return default


def download_xpt_if_needed(ds_id, entry):
    """Same caching convention as etl_v2.py's download_xpt, but usable
    standalone here without needing the rest of that module."""
    xpt_path = f"/tmp/{ds_id}.xpt"
    if os.path.exists(xpt_path):
        return xpt_path

    doc_url = entry["url"]
    xpt_url = doc_url.replace(".htm", ".xpt").replace(".html", ".xpt")
    print(f"  Downloading {xpt_url}...")
    req = urllib.request.Request(xpt_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(xpt_path, "wb") as f:
            f.write(r.read())
    return xpt_path


def get_variables_from_xpt(ds_id, entry):
    """Fallback for datasets where schema.json's variables list is
    empty (extractor.py never populated it). SAS .xpt files embed
    their own column names and labels, so we can read that metadata
    directly from the file instead of depending on schema.json at all."""
    xpt_path = download_xpt_if_needed(ds_id, entry)
    _, meta = pyreadstat.read_xport(xpt_path, encoding="latin1", metadataonly=True)
    labels = meta.column_names_to_labels or {}
    return [
        {"name": col, "label": labels.get(col, "")}
        for col in meta.column_names
    ]


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_concept_table_spec.py <ds_id1> <ds_id2> ...")
        sys.exit(1)

    ds_ids = sys.argv[1:]
    schema = json.load(open("schema.json"))

    os.makedirs("dqd/concept_specs", exist_ok=True)

    for ds_id in ds_ids:
        entry = schema.get(ds_id)
        if not entry:
            print(f"SKIP: {ds_id} not found in schema.json")
            continue

        variables = entry.get("variables", [])
        if not variables:
            print(f"  schema.json has no variables for {ds_id} -- "
                  f"reading columns directly from the .xpt file instead.")
            try:
                variables = get_variables_from_xpt(ds_id, entry)
            except Exception as e:
                print(f"SKIP: {ds_id} -- could not read .xpt file either: {e}")
                continue

        if not variables:
            print(f"SKIP: {ds_id} -- .xpt file has no columns either. Nothing to specify.")
            continue

        columns = [v["name"] for v in variables]
        var_descriptions = "\n".join(
            f"  {v['name']}: {v.get('label', '')}" for v in variables
        )

        try:
            sample_rows = get_sample_rows(ds_id, entry, n=5)
        except Exception as e:
            print(f"  WARNING: could not read sample rows ({e}); "
                  f"proceeding with column names/labels only.")
            sample_rows = []

        prompt = PROMPT_TEMPLATE.format(
            columns=", ".join(columns),
            variables=var_descriptions,
            n_samples=len(sample_rows),
            sample_rows=json.dumps(sample_rows, indent=2, default=str),
        )

        print(f"\n{'='*60}\n{ds_id}\n{'='*60}")
        reply = nim_chat([
            {"role": "system", "content": SYSTEM_CONCEPT_SPEC},
            {"role": "user", "content": prompt},
        ])
        print(f"--- RAW LLM REPLY (before JSON parsing) ---\n{reply}\n--- END RAW REPLY ---")
        spec = safe_json(reply, default={})

        # Sanity check: the columns the LLM named must actually exist
        # in the file. This is what would have caught varlk_c-2003's
        # invented "FFQ_VAR_VALUE" column automatically.
        if spec:
            for key in ("concept_name_column", "concept_code_column"):
                if spec.get(key) and spec[key] not in columns:
                    print(f"  WARNING: spec's {key}='{spec[key]}' is NOT a real "
                          f"column in this file (real columns: {columns}). "
                          f"This spec needs manual review before use.")
                    spec[f"{key}_INVALID"] = True

        spec_path = f"dqd/concept_specs/spec_{ds_id}.json"
        with open(spec_path, "w") as f:
            json.dump(spec, f, indent=2)

        print(json.dumps(spec, indent=2))
        print(f"Saved: {spec_path}")
        time.sleep(10)


if __name__ == "__main__":
    main()
