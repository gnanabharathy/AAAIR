import os, sys, json, re, urllib.request
import pandas as pd
import psycopg2
import pyreadstat

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
for line in open(".env").read().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

NIM_API_KEY  = os.getenv("NIM_API_KEY", "")
NIM_MODEL    = os.getenv("NIM_MODEL", "meta/llama-3.3-70b-instruct")
NIM_BASE_URL = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

DB_CONFIG = {
    "host":     "localhost",
    "port":     5433,
    "dbname":   "omop",
    "user":     "omop_user",
    "password": "omop_pass",
}

# ---------------------------------------------------------------------------
# NIM helpers
# ---------------------------------------------------------------------------

def nim_chat(messages, max_tokens=4096):
    import json as j
    payload = j.dumps({
        "model": NIM_MODEL, "messages": messages,
        "max_tokens": max_tokens, "temperature": 0.0,
    }).encode()
    req = urllib.request.Request(
        f"{NIM_BASE_URL}/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {NIM_API_KEY}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]

def safe_json(text, default):
    text = re.sub(r'^```[a-z]*\n?', '', text.strip(), flags=re.I)
    text = re.sub(r'\n?```$', '', text.strip())
    try:
        return json.loads(text)
    except:
        for ch in ('[', '{'):
            i = text.find(ch)
            if i != -1:
                try: return json.loads(text[i:])
                except: pass
    return default

# ---------------------------------------------------------------------------
# Step 1 — Download .xpt file
# ---------------------------------------------------------------------------

def download_xpt(ds_id, schema):
    entry = schema.get(ds_id)
    if not entry:
        raise ValueError(f"Dataset {ds_id} not found in schema.json")

    doc_url  = entry["url"]
    # Convert doc URL to data URL
    # e.g. .../DataFiles/DEMO_I.htm → .../DataFiles/DEMO_I.xpt
    xpt_url  = doc_url.replace(".htm", ".xpt").replace(".html", ".xpt")
    xpt_path = f"/tmp/{ds_id}.xpt"

    if os.path.exists(xpt_path):
        print(f"  .xpt already downloaded: {xpt_path}")
        return xpt_path

    print(f"  Downloading {xpt_url}...")
    req = urllib.request.Request(xpt_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        with open(xpt_path, "wb") as f:
            f.write(r.read())
    print(f"  Saved to {xpt_path}")
    return xpt_path

# ---------------------------------------------------------------------------
# Step 2 — NIM generates OMOP mapping
# ---------------------------------------------------------------------------

SYSTEM_ETL = """You are an OMOP CDM expert specialising in NHANES data.
Your job is to map NHANES variables to OMOP CDM 5.4 tables and fields.
Return ONLY valid JSON, no markdown fences, no explanation."""

def nim_generate_mapping(ds_id, variables):
    # Send variables in batches to avoid token limits
    slim = [
        {
            "name":         v["name"],
            "label":        v["label"],
            "english_text": v.get("english_text"),
            "data_type":    v.get("data_type"),
            "values":       v.get("values", [])[:5],
        }
        for v in variables
    ]

    prompt = """Map each NHANES variable to OMOP CDM 5.4.
Return a JSON array where each element has:
  "nhanes_var"     – NHANES variable name (e.g. "RIAGENDR")
  "omop_table"     – OMOP table name (e.g. "person", "measurement", "observation")
                     Use "skip" if this variable should not be mapped
  "omop_field"     – OMOP field name (e.g. "gender_concept_id")
  "concept_id"     – OMOP standard concept_id (integer) or null if unknown
  "notes"          – brief explanation of the mapping decision

Common mappings for NHANES Demographics:
- SEQN → person.person_id (identifier)
- RIAGENDR → person.gender_concept_id (8507=Male, 8532=Female)
- RIDAGEYR → person.year_of_birth (calculate from age)
- RIDRETH1/RIDRETH3 → person.race_concept_id, person.ethnicity_concept_id
- WTINT2YR, WTMEC2YR → observation (survey weights)
- Income variables → observation

VARIABLES:
""" + json.dumps(slim, ensure_ascii=False)

    reply = nim_chat([
        {"role": "system", "content": SYSTEM_ETL},
        {"role": "user",   "content": prompt},
    ])
    return safe_json(reply, default=[])

# ---------------------------------------------------------------------------
# Step 3 — ETL: load .xpt and insert into OMOP tables
# ---------------------------------------------------------------------------

def run_etl(ds_id, xpt_path, mapping, schema_entry):
    print(f"  Loading {xpt_path}...")
    df, meta = pyreadstat.read_xport(xpt_path, encoding="latin1")
    print(f"  {len(df)} rows, {len(df.columns)} columns")

    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    # Disable foreign key checks (concept table is empty)
    cur.execute("SET session_replication_role = replica;")

    # Build mapping dict: nhanes_var → mapping info
    map_dict = {m["nhanes_var"]: m for m in mapping if m.get("omop_table") != "skip"}

    # Insert into person table
    person_rows = _build_person_rows(df, map_dict)
    if person_rows:
        print(f"  Inserting {len(person_rows)} rows into person...")
        # Clear existing data first to avoid duplicates
        cur.execute("DELETE FROM public.observation WHERE person_id = ANY(%s)", ([r[0] for r in person_rows],))
        cur.execute("DELETE FROM public.person WHERE person_id = ANY(%s)",
                    ([r[0] for r in person_rows],))
        cur.executemany("""
            INSERT INTO public.person (
                person_id, gender_concept_id, year_of_birth,
                race_concept_id, ethnicity_concept_id,
                gender_source_value, race_source_value
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, person_rows)

    # Insert survey weights and other variables into observation
    obs_rows = _build_observation_rows(df, map_dict)
    if obs_rows:
        # Get current max observation_id to avoid duplicates
        cur.execute("SELECT COALESCE(MAX(observation_id), 0) FROM public.observation")
        max_obs_id = cur.fetchone()[0]
        obs_rows = [(max_obs_id + i + 1,) + row[1:] for i, row in enumerate(obs_rows)]
        print(f"  Inserting {len(obs_rows)} rows into observation (starting id={max_obs_id+1})...")
        cur.executemany("""
            INSERT INTO public.observation (
                observation_id, person_id, observation_concept_id,
                observation_date, observation_type_concept_id,
                value_as_number, value_as_string, observation_source_value
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, obs_rows)

    cur.execute("SET session_replication_role = DEFAULT;")    
    conn.commit()
    cur.close()
    conn.close()
    print(f"  ETL complete.")

def _build_person_rows(df, map_dict):
    rows = []
    gender_map = {"1": 8507, "2": 8532}  # OMOP concept IDs
    race_map   = {"1": 8527, "2": 8527, "3": 8527, "4": 8516, "5": 8522}

    for _, row in df.iterrows():
        seqn = int(row.get("SEQN", 0))
        if not seqn:
            continue

        gender_val  = str(int(row["RIAGENDR"])) if "RIAGENDR" in row and pd.notna(row["RIAGENDR"]) else None
        age         = int(row["RIDAGEYR"]) if "RIDAGEYR" in row and pd.notna(row["RIDAGEYR"]) else None
        race_val    = str(int(row["RIDRETH1"])) if "RIDRETH1" in row and pd.notna(row["RIDRETH1"]) else None

        rows.append((
            seqn,
            gender_map.get(gender_val, 0),
            2015 - age if age else 0,   # approximate birth year
            race_map.get(race_val, 0),
            0,                             # ethnicity_concept_id
            gender_val,
            race_val,
        ))
    return rows

def _build_observation_rows(df, map_dict):
    from datetime import date
    rows = []
    obs_vars = ["WTINT2YR", "WTMEC2YR", "INDFMPIR", "INDHHIN2"]
    idx = 0
    for _, row in df.iterrows():
        seqn = int(row.get("SEQN", 0))
        if not seqn:
            continue
        for var in obs_vars:
            if var in row and pd.notna(row[var]):
                rows.append((
                    idx, seqn, 0,
                    date(2015, 1, 1), 44818702,
                    float(row[var]), None, var
                ))
                idx += 1
    return rows

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 etl.py <dataset-id>")
        print("Example: python3 etl.py nhanes-demographics-demo_i-2015")
        sys.exit(1)

    ds_id = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"ETL: {ds_id}")
    print(f"{'='*60}")

    # Load schema
    schema = json.load(open("schema.json"))
    entry  = schema.get(ds_id)
    if not entry:
        print(f"ERROR: {ds_id} not found in schema.json")
        sys.exit(1)

    variables = entry["variables"]
    print(f"  {len(variables)} variables in schema")

    # Step 1: Download .xpt
    print("\n[1/3] Downloading .xpt file...")
    xpt_path = download_xpt(ds_id, schema)

    # Step 2: NIM generates mapping
    print("\n[2/3] NIM generating OMOP mapping...")
    mapping = nim_generate_mapping(ds_id, variables)
    print(f"  {len(mapping)} variables mapped")

    # Save mapping for inspection
    mapping_path = f"mapping_{ds_id}.json"
    with open(mapping_path, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"  Mapping saved to {mapping_path}")

    # Step 3: ETL
    print("\n[3/3] Running ETL...")
    run_etl(ds_id, xpt_path, mapping, entry)

    print(f"\nDone! Data loaded into PostgreSQL (omop database)")
    print(f"Next step: run DQD in R")

if __name__ == "__main__":
    main()