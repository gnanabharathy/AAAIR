import os, sys, json, re, urllib.request, time
from datetime import date
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
NIM_MODEL    = os.getenv("NIM_MODEL")
NIM_BASE_URL = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

DB_CONFIG = {
    "host":     "localhost",
    "port":     5433,
    "dbname":   "omop",
    "user":     "omop_user",
    "password": "omop_pass",
}

BATCH_SIZE = 15  # variables per NIM call

# ---------------------------------------------------------------------------
# NIM helpers
# ---------------------------------------------------------------------------

def nim_chat(messages, max_tokens=4096, retries=3):
    import time
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
            with urllib.request.urlopen(req, timeout=300) as r:
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
    xpt_url  = doc_url.replace(".htm", ".xpt").replace(".html", ".xpt")
    xpt_path = f"/tmp/{ds_id}.xpt"

    if os.path.exists(xpt_path):
        print(f"  .xpt already downloaded: {xpt_path}")
        return xpt_path

    print(f"  Downloading {xpt_url}...")
    req = urllib.request.Request(xpt_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(xpt_path, "wb") as f:
            f.write(r.read())
    print(f"  Saved to {xpt_path}")
    return xpt_path

# ---------------------------------------------------------------------------
# Step 2 — LLM generates OMOP mapping (batched, no hardcoded rules)
# ---------------------------------------------------------------------------

SYSTEM_ETL = """You are an OMOP CDM 5.3 expert specialising in NHANES data.
Your job is to map NHANES variables to OMOP CDM 5.3 tables and fields.
Return ONLY valid JSON array, no markdown fences, no explanation."""

PROMPT_TEMPLATE = """Map each NHANES variable to the most appropriate OMOP CDM 5.3 table and field.
Return ONLY a JSON array. Each element must have:
  "nhanes_var"  - NHANES variable name
  "omop_table"  - OMOP CDM 5.3 table name
  "omop_field"  - OMOP CDM 5.3 field name
  "concept_id"  - OMOP standard concept_id (integer) or null
  "notes"       - brief explanation

VARIABLES:
"""

def nim_generate_mapping(ds_id, variables):
    slim = [
        {
            "name":      v["name"],
            "label":     v["label"],
            "data_type": v.get("data_type"),
        }
        for v in variables
    ]

    all_mappings = []
    for i in range(0, len(slim), BATCH_SIZE):
        batch = slim[i:i + BATCH_SIZE]
        prompt = PROMPT_TEMPLATE + json.dumps(batch, ensure_ascii=False)
        reply = nim_chat([
            {"role": "system", "content": SYSTEM_ETL},
            {"role": "user",   "content": prompt},
        ])
        batch_result = safe_json(reply, default=[])
        all_mappings.extend(batch_result)
        print(f"  Batch {i//BATCH_SIZE + 1}: {len(batch_result)} variables mapped")
        time.sleep(30)

    return all_mappings

# ---------------------------------------------------------------------------
# Step 3 — ETL: insert into OMOP tables based on LLM mapping
# ---------------------------------------------------------------------------

def run_etl(ds_id, xpt_path, mapping, schema_entry):
    print(f"  Loading {xpt_path}...")
    df, meta = pyreadstat.read_xport(xpt_path, encoding="latin1")
    print(f"  {len(df)} rows, {len(df.columns)} columns")

    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    cur.execute("SET session_replication_role = replica;")

    # Build mapping dict: nhanes_var → mapping info
    map_dict = {
        m["nhanes_var"]: m
        for m in mapping
        if m.get("omop_table") and m.get("omop_table").lower() != "skip"
    }

    # Get all person_ids (SEQN) in this dataset for cleanup
    seqns = [int(row["SEQN"]) for _, row in df.iterrows() if "SEQN" in row and pd.notna(row["SEQN"])]

    # Group mapping by target table
    DEMO_FIELDS = {"gender_concept_id", "year_of_birth", "race_concept_id", "ethnicity_concept_id"}
    person_vars   = {k: v for k, v in map_dict.items() if v.get("omop_table", "").lower() == "person"}
    measure_vars  = {k: v for k, v in map_dict.items() if v.get("omop_table", "").lower() == "measurement"}
    obs_vars      = {k: v for k, v in map_dict.items() if v.get("omop_table", "").lower() == "observation"}

    # --- person table ---
    has_demo = any(v.get("omop_field", "") in DEMO_FIELDS for v in person_vars.values()) if person_vars else False
    if person_vars and has_demo:
        person_rows = _build_person_rows(df, person_vars)
        if person_rows:
            cur.execute("DELETE FROM public.person WHERE person_id = ANY(%s)", ([r[0] for r in person_rows],))
            cur.execute("DELETE FROM public.observation WHERE person_id = ANY(%s)", ([r[0] for r in person_rows],))
            cur.execute("DELETE FROM public.measurement WHERE person_id = ANY(%s)", ([r[0] for r in person_rows],))
            print(f"  Inserting {len(person_rows)} rows into person...")
            cur.executemany("""
                INSERT INTO public.person (
                    person_id, gender_concept_id, year_of_birth,
                    race_concept_id, ethnicity_concept_id,
                    gender_source_value, race_source_value
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (person_id) DO NOTHING
            """, person_rows)

    # --- measurement table ---
    if measure_vars:
        cur.execute("SELECT COALESCE(MAX(measurement_id), 0) FROM public.measurement")
        max_id = cur.fetchone()[0]
        meas_rows = _build_measurement_rows(df, measure_vars, start_id=max_id + 1)
        if meas_rows:
            print(f"  Inserting {len(meas_rows)} rows into measurement...")
            cur.executemany("""
                INSERT INTO public.measurement (
                    measurement_id, person_id, measurement_concept_id,
                    measurement_date, measurement_type_concept_id,
                    value_as_number, unit_concept_id, measurement_source_value
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, meas_rows)

    # --- observation table ---
    if obs_vars:
        cur.execute("SELECT COALESCE(MAX(observation_id), 0) FROM public.observation")
        max_id = cur.fetchone()[0]
        obs_rows = _build_observation_rows(df, obs_vars, start_id=max_id + 1)
        if obs_rows:
            print(f"  Inserting {len(obs_rows)} rows into observation...")
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

# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def _build_person_rows(df, person_vars):
    rows = []
    gender_map = {"1": 8507, "2": 8532}
    race_map   = {"1": 8527, "2": 8527, "3": 8527, "4": 8516, "5": 8522}

    # Find which columns map to which person fields
    gender_col = next((k for k, v in person_vars.items() if "gender" in v.get("omop_field", "").lower()), None)
    age_col    = next((k for k, v in person_vars.items() if "year_of_birth" in v.get("omop_field", "").lower() or "age" in v.get("notes", "").lower()), None)
    race_col   = next((k for k, v in person_vars.items() if "race" in v.get("omop_field", "").lower()), None)

    for _, row in df.iterrows():
        seqn = int(row.get("SEQN", 0)) if pd.notna(row.get("SEQN", 0)) else 0
        if not seqn:
            continue

        gender_val = str(int(row[gender_col])) if gender_col and gender_col in row and pd.notna(row[gender_col]) else None
        age        = int(row[age_col]) if age_col and age_col in row and pd.notna(row[age_col]) else None
        race_val   = str(int(row[race_col])) if race_col and race_col in row and pd.notna(row[race_col]) else None

        # Estimate birth year from age (use dataset year if available)
        birth_year = (2015 - age) if age is not None else 0

        rows.append((
            seqn,
            gender_map.get(gender_val, 0),
            birth_year,
            race_map.get(race_val, 0),
            0,
            gender_val,
            race_val,
        ))
    return rows

def _build_measurement_rows(df, measure_vars, start_id=1):
    rows = []
    obs_id = start_id

    # Aggregate by SEQN (sum numeric vars per person)
    num_vars = [v for v in measure_vars.keys() if v in df.columns and pd.api.types.is_numeric_dtype(df[v])]
    if not num_vars:
        return rows

    agg_df = df.groupby("SEQN")[num_vars].sum().reset_index()

    for _, row in agg_df.iterrows():
        seqn = int(row["SEQN"]) if pd.notna(row["SEQN"]) else 0
        if not seqn:
            continue
        for var, mapping in measure_vars.items():
            if var in row and pd.notna(row[var]):
                try:
                    val = float(row[var])
                except (ValueError, TypeError):
                    continue
                rows.append((
                    obs_id, seqn,
                    mapping.get("concept_id") or 0,
                    date(2015, 1, 1),
                    44818702,
                    val,
                    0,
                    var,
                ))
                obs_id += 1
    return rows

def _build_observation_rows(df, obs_vars, start_id=1):
    rows = []
    obs_id = start_id
    MAX_STR_LEN = 60  # matches observation.value_as_string varchar(60)

    for _, row in df.iterrows():
        seqn = int(row.get("SEQN", 0)) if pd.notna(row.get("SEQN", 0)) else 0
        if not seqn:
            continue
        for var, mapping in obs_vars.items():
            if var in row and pd.notna(row[var]):
                raw = row[var]
                try:
                    val_num = float(raw)
                    val_str = None
                except (ValueError, TypeError):
                    val_num = None
                    val_str = str(raw).strip()
                    if len(val_str) > MAX_STR_LEN:
                        val_str = val_str[:MAX_STR_LEN]

                rows.append((
                    obs_id, seqn,
                    mapping.get("concept_id") or 0,
                    date(2015, 1, 1),
                    44818702,
                    val_num, val_str, var[:MAX_STR_LEN],  # var 一般不会超长，加个保险
                ))
                obs_id += 1
    return rows

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 etl_v2.py <dataset-id>")
        print("Example: python3 etl_v2.py nhanes-dietary-drxiff_b-2001")
        sys.exit(1)

    ds_id = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"ETL v2: {ds_id}")
    print(f"{'='*60}")

    schema = json.load(open("schema.json"))
    entry  = schema.get(ds_id)
    if not entry:
        print(f"ERROR: {ds_id} not found in schema.json")
        sys.exit(1)

    variables = entry.get("variables", [])
    category  = entry.get("subtypes", ["unknown"])[0]
    print(f"  Category: {category}")
    print(f"  Variables in schema: {len(variables)}")

    # Step 1: Download .xpt
    print("\n[1/3] Downloading .xpt file...")
    xpt_path = download_xpt(ds_id, schema)

    # Step 2: LLM generates mapping
    print("\n[2/3] LLM generating OMOP mapping...")
    mapping = nim_generate_mapping(ds_id, variables)
    print(f"  Total: {len(mapping)} variables mapped")

    os.makedirs("dqd/mapping", exist_ok=True)
    mapping_path = f"dqd/mapping/mapping_{ds_id}.json"
    with open(mapping_path, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"  Mapping saved to {mapping_path}")

    # Step 3: ETL
    print("\n[3/3] Running ETL...")
    run_etl(ds_id, xpt_path, mapping, entry)

    print(f"\nDone! Data loaded into PostgreSQL.")
    print(f"Next step: Rscript dqd.R {ds_id} \"{entry.get('name', ds_id)}\"")

if __name__ == "__main__":
    main()
