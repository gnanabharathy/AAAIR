"""
generate_simple_column_roles.py

Minimal fallback for datasets where generate_concept_table_spec.py's
full 7-field prompt triggers a runaway reasoning loop (seen with
nhanes-dietary-drxmcd_e-2007 -- the model got stuck repeating "Let's
propose X domain... but we can also propose X domain..." for
thousands of tokens without ever converging, twice in a row).

This asks ONE much simpler question -- which column is the name and
which is the code -- with real sample data shown, and nothing else.
domain_id/vocabulary_id/concept_class_id are left as null placeholders
for harmonize_concept_specs.py (or a manual family-level decision) to
fill in afterward, since those are the fields that seem to trigger the
over-thinking in the first place.

Usage: python3 generate_simple_column_roles.py <ds_id>
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

SYSTEM_SIMPLE = """You identify which column in a small reference table holds a
human-readable name versus a short code/identifier.
Return ONLY valid JSON, no markdown fences, no explanation, no reasoning text."""

PROMPT_TEMPLATE = """Columns: {columns}

Sample rows:
{sample_rows}

Which column holds the human-readable name, and which holds the short code/identifier?
Return ONLY this JSON object:
{{"name_column": "...", "code_column": "..."}}
"""


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


def nim_chat(messages, max_tokens=512, retries=3):
    """Deliberately small max_tokens -- if the model starts spiraling
    into repetitive reasoning again, it gets cut off fast and we find
    out quickly rather than burning a long timeout."""
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
            with urllib.request.urlopen(req, timeout=60) as r:
                msg = json.loads(r.read())["choices"][0]["message"]
                return msg.get("content") or msg.get("reasoning_content") or ""
        except Exception as e:
            print(f"  NIM attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(30)
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
        print("Usage: python3 generate_simple_column_roles.py <ds_id>")
        sys.exit(1)

    ds_id = sys.argv[1]
    schema = json.load(open("schema.json"))
    entry = schema[ds_id]

    xpt_path = download_xpt_if_needed(ds_id, entry)
    df, meta = pyreadstat.read_xport(xpt_path, encoding="latin1")
    columns = list(df.columns)
    sample_rows = df.head(5).to_dict(orient="records")

    prompt = PROMPT_TEMPLATE.format(
        columns=", ".join(columns),
        sample_rows=json.dumps(sample_rows, indent=2, default=str),
    )

    print(f"Asking simplified question for {ds_id}...")
    reply = nim_chat([
        {"role": "system", "content": SYSTEM_SIMPLE},
        {"role": "user", "content": prompt},
    ])
    print(f"--- RAW REPLY ---\n{reply}\n--- END ---")

    result = safe_json(reply, default={})
    if not result or "name_column" not in result:
        print("Still failed to get a usable answer. Stopping here for manual review.")
        return

    if result["name_column"] not in columns or result["code_column"] not in columns:
        print(f"WARNING: returned columns not in actual file columns {columns}. Review manually.")
        return

    spec = {
        "concept_name_column": result["name_column"],
        "concept_code_column": result["code_column"],
        "domain_id": None,
        "vocabulary_id": None,
        "concept_class_id": None,
        "one_row_per_concept": True,
        "additional_columns_as_synonyms": [],
        "notes": (
            "Generated via simplified fallback prompt (generate_simple_column_roles.py) "
            "after the full spec prompt triggered a runaway reasoning loop twice. "
            "domain_id/vocabulary_id/concept_class_id intentionally left null -- "
            "fill in via harmonize_concept_specs.py against sibling files in the same family."
        ),
    }

    spec_path = f"dqd/concept_specs/spec_{ds_id}.json"
    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"Saved: {spec_path}")
    print(json.dumps(spec, indent=2))


if __name__ == "__main__":
    main()
