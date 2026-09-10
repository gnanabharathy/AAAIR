"""
harmonize_concept_specs.py

Individual generate_concept_table_spec.py runs (one LLM call per
dataset) can produce inconsistent domain_id/vocabulary_id/
concept_class_id across files that are actually the same underlying
reference vocabulary sampled in different NHANES survey cycles (e.g.
drxfcd_c-2003 through drxfcd_l-2021 are all "USDA food code
descriptions", just from different years -- they should all land in
the same local vocabulary, not scattered across "Food"/"Dietary"/
"Observation" domains with different vocabulary_id values).

This script takes a family of ds_ids that share the same existing
specs (from dqd/concept_specs/spec_{ds_id}.json), shows the LLM all of
them together, and asks IT to decide on one harmonized domain_id/
vocabulary_id/concept_class_id that all of them should share -- column
name choices (concept_name_column/concept_code_column) are preserved
per-dataset in case they genuinely differ between years, but the
vocabulary-level identity is unified.

Usage:
    python3 harmonize_concept_specs.py <ds_id1> <ds_id2> ...
"""

import json
import os
import re
import sys
import time
import urllib.request

for line in open(".env").read().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

NIM_API_KEY = os.getenv("NIM_API_KEY", "")
NIM_MODEL = os.getenv("NIM_MODEL")
NIM_BASE_URL = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

SYSTEM_HARMONIZE = """You are an OMOP CDM 5.3 vocabulary expert.
You are given several independently-generated concept-table mapping
specs for NHANES reference files that are the SAME underlying kind of
data, just sampled in different survey cycles/years. Because they were
generated independently, their domain_id/vocabulary_id/concept_class_id
may be inconsistent across years even though they should represent one
coherent local vocabulary.
Your job is to decide ONE harmonized domain_id, vocabulary_id, and
concept_class_id that ALL of these datasets should share, so that
concepts from different years end up in the same vocabulary rather
than scattered across inconsistent ones.
Return ONLY valid JSON, no markdown fences, no explanation."""

PROMPT_TEMPLATE = """Here are the individually-generated specs for {n} files that are all the same
kind of NHANES reference data across different survey years:

{specs}

Return ONLY a JSON object with these exact keys:
  "harmonized_domain_id"        - the single domain_id all of these should share
  "harmonized_vocabulary_id"    - the single vocabulary_id all of these should share
  "harmonized_concept_class_id" - the single concept_class_id all of these should share
  "reasoning"                    - brief explanation of why you chose these values over the alternatives seen above
"""


def nim_chat(messages, max_tokens=4096, retries=3):
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


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 harmonize_concept_specs.py <ds_id1> <ds_id2> ...")
        sys.exit(1)

    ds_ids = sys.argv[1:]
    specs = {}
    for ds_id in ds_ids:
        spec_path = f"dqd/concept_specs/spec_{ds_id}.json"
        if not os.path.exists(spec_path):
            print(f"SKIP: no existing spec found at {spec_path}")
            continue
        specs[ds_id] = json.load(open(spec_path))

    if len(specs) < 2:
        print("Need at least 2 existing specs to harmonize. Aborting.")
        return

    specs_text = json.dumps(specs, indent=2)
    prompt = PROMPT_TEMPLATE.format(n=len(specs), specs=specs_text)

    print(f"Harmonizing {len(specs)} specs: {list(specs.keys())}")
    reply = nim_chat([
        {"role": "system", "content": SYSTEM_HARMONIZE},
        {"role": "user", "content": prompt},
    ])
    print(f"--- RAW LLM REPLY ---\n{reply}\n--- END RAW REPLY ---")

    harmonized = safe_json(reply, default={})
    if not harmonized:
        print("Harmonization failed to parse -- nothing was changed.")
        return

    print(f"\nHarmonized values:\n{json.dumps(harmonized, indent=2)}")

    # Apply the harmonized domain/vocabulary/concept_class to each
    # dataset's individual spec, preserving their own column choices.
    for ds_id, spec in specs.items():
        spec["domain_id"] = harmonized["harmonized_domain_id"]
        spec["vocabulary_id"] = harmonized["harmonized_vocabulary_id"]
        spec["concept_class_id"] = harmonized["harmonized_concept_class_id"]
        spec["harmonization_reasoning"] = harmonized.get("reasoning", "")

        spec_path = f"dqd/concept_specs/spec_{ds_id}.json"
        with open(spec_path, "w") as f:
            json.dump(spec, f, indent=2)
        print(f"  Updated: {spec_path}")


if __name__ == "__main__":
    main()
