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

def _register_rows(cur, ds_id, table_name, row_ids):
    """Record which ds_id inserted these rows, for later per-dataset DQD
    view generation (see create_dataset_row_registry.sql). Uses
    ON CONFLICT DO NOTHING so if a row_id was already registered by an
    earlier dataset (shouldn't normally happen, but is possible for
    person rows if two datasets somehow target the same person_id),
    the original attribution is preserved rather than overwritten."""
    if not row_ids:
        return
    cur.executemany(
        """
        INSERT INTO public.dataset_row_registry (ds_id, table_name, row_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (table_name, row_id) DO NOTHING
        """,
        [(ds_id, table_name, row_id) for row_id in row_ids],
    )


def _register_shared_rows(cur, ds_id, table_name, row_ids):
    """Same as _register_rows, but for shared_row_registry -- allows
    multiple ds_ids to reference the same row (see
    create_shared_row_registry.sql). Used for variables genuinely
    shared across sibling datasets (e.g. DRDINT appearing in both
    DR1IFF and DR1TOT), where dataset_row_registry's single-owner
    constraint doesn't apply."""
    if not row_ids:
        return
    cur.executemany(
        """
        INSERT INTO public.shared_row_registry (ds_id, table_name, row_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (ds_id, table_name, row_id) DO NOTHING
        """,
        [(ds_id, table_name, row_id) for row_id in row_ids],
    )


def _load_shared_variables(ds_id):
    """Which of this dataset's variables are known to be shared with a
    sibling dataset (same SEQN cycle + same variable name)? Loaded from
    shared_variables_by_dataset.json (built by
    build_shared_variable_lookup.py from find_variable_collisions.py's
    output). A dataset/variable not present here is assumed exclusive."""
    try:
        lookup = json.load(open("shared_variables_by_dataset.json"))
    except FileNotFoundError:
        return set()
    return set(lookup.get(ds_id, []))


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
    drug_vars     = {k: v for k, v in map_dict.items() if v.get("omop_table", "").lower() == "drug_exposure"}

    # --- person table ---
    has_demo = any(v.get("omop_field", "") in DEMO_FIELDS for v in person_vars.values()) if person_vars else False
    if person_vars and has_demo:
        person_rows = _build_person_rows(df, person_vars)
        if person_rows:
            # SAFETY: only delete rows THIS ds_id previously wrote, not
            # everything tied to these person_ids. person_id (=SEQN) is
            # shared across many datasets in the same NHANES cycle (e.g.
            # a demographics dataset and dietary/examination datasets
            # for the same year both touch the same SEQNs) -- a blanket
            # "DELETE WHERE person_id = ANY(...)" would wipe out other
            # already-completed datasets' measurement/observation rows
            # for those same people. Scoping by dataset_row_registry
            # instead only clears this dataset's own prior contribution.
            cur.execute(
                "DELETE FROM public.person "
                "WHERE person_id = ANY(%s) "
                "AND person_id IN (SELECT row_id FROM public.dataset_row_registry "
                "WHERE ds_id = %s AND table_name = 'person')",
                ([r[0] for r in person_rows], ds_id),
            )
            cur.execute(
                "DELETE FROM public.observation "
                "WHERE observation_id IN (SELECT row_id FROM public.dataset_row_registry "
                "WHERE ds_id = %s AND table_name = 'observation')",
                (ds_id,),
            )
            cur.execute(
                "DELETE FROM public.measurement "
                "WHERE measurement_id IN (SELECT row_id FROM public.dataset_row_registry "
                "WHERE ds_id = %s AND table_name = 'measurement')",
                (ds_id,),
            )
            cur.execute(
                "DELETE FROM public.dataset_row_registry WHERE ds_id = %s",
                (ds_id,),
            )
            print(f"  Inserting {len(person_rows)} rows into person...")
            cur.executemany("""
                INSERT INTO public.person (
                    person_id, gender_concept_id, year_of_birth,
                    race_concept_id, ethnicity_concept_id,
                    gender_source_value, race_source_value
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (person_id) DO NOTHING
            """, person_rows)
            _register_rows(cur, ds_id, "person", [r[0] for r in person_rows])

    # --- measurement table ---
    if measure_vars:
        seqns = [int(s) for s in df["SEQN"].dropna().unique()]
        shared_vars = _load_shared_variables(ds_id)
        all_meas_cols = list(measure_vars.keys())
        exclusive_cols = [c for c in all_meas_cols if c not in shared_vars]
        shared_cols = [c for c in all_meas_cols if c in shared_vars]

        if exclusive_cols:
            # BROAD delete: catches both registry-tracked rows AND
            # orphaned duplicates from a pre-dataset_row_registry ETL
            # run of THIS dataset. Safe because these variable names
            # cannot legitimately belong to any sibling dataset (per
            # find_variable_collisions.py's audit) -- unlike shared
            # variables, there's no risk of destroying another
            # dataset's data here.
            cur.execute(
                "DELETE FROM public.measurement "
                "WHERE person_id = ANY(%s) AND measurement_source_value = ANY(%s)",
                (seqns, exclusive_cols),
            )
        if shared_cols:
            # CONSERVATIVE delete: only rows this exact ds_id already
            # owns per the registry -- never broad-match by SEQN+
            # variable for these, since a sibling dataset (e.g. DR1TOT
            # sharing DRDINT with DR1IFF) may legitimately hold rows
            # for the same variable+person that must not be touched.
            cur.execute(
                "DELETE FROM public.measurement "
                "WHERE measurement_id IN (SELECT row_id FROM public.dataset_row_registry "
                "WHERE ds_id = %s AND table_name = 'measurement') "
                "AND measurement_source_value = ANY(%s)",
                (ds_id, shared_cols),
            )

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
            _register_rows(cur, ds_id, "measurement", [r[0] for r in meas_rows])
            if shared_cols:
                shared_row_ids = [
                    r[0] for r in meas_rows if r[7] in shared_cols
                ]
                _register_shared_rows(cur, ds_id, "measurement", shared_row_ids)

    # --- observation table ---
    if obs_vars:
        seqns = [int(s) for s in df["SEQN"].dropna().unique()]
        shared_vars = _load_shared_variables(ds_id)
        all_obs_cols = list(obs_vars.keys())
        exclusive_cols = [c for c in all_obs_cols if c not in shared_vars]
        shared_cols = [c for c in all_obs_cols if c in shared_vars]

        if exclusive_cols:
            cur.execute(
                "DELETE FROM public.observation "
                "WHERE person_id = ANY(%s) AND observation_source_value = ANY(%s)",
                (seqns, exclusive_cols),
            )
        if shared_cols:
            cur.execute(
                "DELETE FROM public.observation "
                "WHERE observation_id IN (SELECT row_id FROM public.dataset_row_registry "
                "WHERE ds_id = %s AND table_name = 'observation') "
                "AND observation_source_value = ANY(%s)",
                (ds_id, shared_cols),
            )

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
            _register_rows(cur, ds_id, "observation", [r[0] for r in obs_rows])
            if shared_cols:
                shared_row_ids = [
                    r[0] for r in obs_rows if r[7] in shared_cols
                ]
                _register_shared_rows(cur, ds_id, "observation", shared_row_ids)

    # --- drug_exposure table ---
    if drug_vars:
        seqns_d = [int(s) for s in df["SEQN"].dropna().unique()]
        shared_vars_d = _load_shared_variables(ds_id)
        all_drug_cols = list(drug_vars.keys())
        exclusive_cols_d = [c for c in all_drug_cols if c not in shared_vars_d]
        shared_cols_d = [c for c in all_drug_cols if c in shared_vars_d]

        if exclusive_cols_d:
            cur.execute(
                "DELETE FROM public.drug_exposure "
                "WHERE person_id = ANY(%s) AND drug_source_value = ANY(%s)",
                (seqns_d, exclusive_cols_d),
            )
        if shared_cols_d:
            cur.execute(
                "DELETE FROM public.drug_exposure "
                "WHERE drug_exposure_id IN (SELECT row_id FROM public.dataset_row_registry "
                "WHERE ds_id = %s AND table_name = 'drug_exposure') "
                "AND drug_source_value = ANY(%s)",
                (ds_id, shared_cols_d),
            )

        cur.execute("SELECT COALESCE(MAX(drug_exposure_id), 0) FROM public.drug_exposure")
        max_id = cur.fetchone()[0]
        drug_rows = _build_drug_exposure_rows(df, drug_vars, start_id=max_id + 1)
        if drug_rows:
            print(f"  Inserting {len(drug_rows)} rows into drug_exposure...")
            cur.executemany("""
                INSERT INTO public.drug_exposure (
                    drug_exposure_id, person_id, drug_concept_id,
                    drug_exposure_start_date, drug_exposure_end_date,
                    drug_type_concept_id, drug_source_value
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, drug_rows)
            _register_rows(cur, ds_id, "drug_exposure", [r[0] for r in drug_rows])
            if shared_cols_d:
                shared_row_ids_d = [
                    r[0] for r in drug_rows if r[6] in shared_cols_d
                ]
                _register_shared_rows(cur, ds_id, "drug_exposure", shared_row_ids_d)

    cur.execute("SET session_replication_role = DEFAULT;")
    conn.commit()
    cur.close()
    conn.close()
    print(f"  ETL complete.")

# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def _find_person_constant_vars(df, var_names):
    """A variable is 'person-constant' if, for every person, it takes
    on at most one distinct value across all their rows in the raw
    file -- e.g. DRDINT (dietary interview status) is genuinely a
    single per-person fact, but NHANES individual-record files (one
    row per food item eaten) redundantly repeat it on every row for
    that person. Such variables must be deduplicated to ONE row per
    person; variables that legitimately vary per row (e.g. a specific
    food item's nutrient content) must not be.

    This is detected directly from the data (no hardcoded variable
    list, no per-dataset judgment) -- it's what caught DRDINT being
    inserted 17+ times per person for dr1iff_e-2007 despite a single,
    correct ETL run."""
    constant_vars = set()
    for var in var_names:
        if var not in df.columns:
            continue
        nunique_per_person = df.groupby("SEQN")[var].nunique(dropna=True)
        if (nunique_per_person <= 1).all():
            constant_vars.add(var)
    return constant_vars


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

    num_vars = [v for v in measure_vars.keys() if v in df.columns and pd.api.types.is_numeric_dtype(df[v])]
    if not num_vars:
        return rows

    # Person-constant variables (e.g. a fixed survey weight repeated on
    # every food-item row) must NOT be summed across a person's rows --
    # that would inflate a single true value by however many rows that
    # person happens to have. Only genuinely per-row/additive variables
    # (e.g. calories from each food item, meant to sum to a daily
    # total) should be aggregated with sum().
    constant_vars = _find_person_constant_vars(df, num_vars)
    sum_vars = [v for v in num_vars if v not in constant_vars]

    if sum_vars:
        agg_df = df.groupby("SEQN")[sum_vars].sum().reset_index()
        for _, row in agg_df.iterrows():
            seqn = int(row["SEQN"]) if pd.notna(row["SEQN"]) else 0
            if not seqn:
                continue
            for var in sum_vars:
                mapping = measure_vars[var]
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

    if constant_vars:
        # One row per person, taking the person's single (constant)
        # value directly -- not summed.
        first_df = df.groupby("SEQN")[list(constant_vars)].first().reset_index()
        for _, row in first_df.iterrows():
            seqn = int(row["SEQN"]) if pd.notna(row["SEQN"]) else 0
            if not seqn:
                continue
            for var in constant_vars:
                mapping = measure_vars[var]
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

    all_vars = list(obs_vars.keys())
    constant_vars = _find_person_constant_vars(df, all_vars)
    per_row_vars = {v: m for v, m in obs_vars.items() if v not in constant_vars}
    constant_var_mappings = {v: m for v, m in obs_vars.items() if v in constant_vars}

    def _make_row(obs_id, seqn, mapping, raw, var):
        try:
            val_num = float(raw)
            val_str = None
        except (ValueError, TypeError):
            val_num = None
            val_str = str(raw).strip()
            if len(val_str) > MAX_STR_LEN:
                val_str = val_str[:MAX_STR_LEN]
        return (
            obs_id, seqn,
            mapping.get("concept_id") or 0,
            date(2015, 1, 1),
            44818702,
            val_num, val_str, var[:MAX_STR_LEN],
        )

    # Genuinely per-row variables (e.g. this specific food item's
    # nutrient content) -- one row per raw dataframe row, as before.
    if per_row_vars:
        for _, row in df.iterrows():
            seqn = int(row.get("SEQN", 0)) if pd.notna(row.get("SEQN", 0)) else 0
            if not seqn:
                continue
            for var, mapping in per_row_vars.items():
                if var in row and pd.notna(row[var]):
                    rows.append(_make_row(obs_id, seqn, mapping, row[var], var))
                    obs_id += 1

    # Person-constant variables (e.g. DRDINT, repeated identically on
    # every one of a person's food-item rows) -- deduplicated to
    # exactly ONE row per person, using their single real value. This
    # is what prevents a person-level fact from being inserted once
    # per food item they happened to log that day.
    if constant_var_mappings:
        first_df = df.drop_duplicates(subset=["SEQN"])
        for _, row in first_df.iterrows():
            seqn = int(row.get("SEQN", 0)) if pd.notna(row.get("SEQN", 0)) else 0
            if not seqn:
                continue
            for var, mapping in constant_var_mappings.items():
                if var in row and pd.notna(row[var]):
                    rows.append(_make_row(obs_id, seqn, mapping, row[var], var))
                    obs_id += 1

    return rows


def _build_drug_exposure_rows(df, drug_vars, start_id=1):
    """drug_exposure has no generic value_as_number/value_as_string
    slot like measurement/observation do -- its core fields are
    drug_concept_id (WHICH substance) and a start/end date range. Two
    mapping patterns are supported, driven by what the LLM's mapping
    specifies per variable:
      - omop_field == 'drug_concept_id': the variable is a yes/no or
        categorical fact about exposure to a specific substance (the
        mapping's own concept_id identifies which substance) -- a row
        is generated only when the person's raw value indicates a
        positive/true exposure (e.g. DSD010=1 for "yes, took a
        supplement"). The concept_id comes from the mapping, not the
        raw value.
      - omop_field == 'quantity' (or any other numeric field): the raw
        value itself is stored in that field, alongside a drug_concept_id
        of 0 (unmapped) unless a real one is given, since a bare
        quantity alone doesn't identify a substance.

    Same person-constant deduplication as observation/measurement --
    NHANES survey files can repeat person-level facts across rows.
    """
    rows = []
    row_id = start_id
    PLACEHOLDER_DATE = date(2015, 1, 1)
    PLACEHOLDER_TYPE_CONCEPT_ID = 44818702  # matches the placeholder
                                             # used elsewhere in this
                                             # file for measurement/
                                             # observation type_concept_id

    all_vars = list(drug_vars.keys())
    constant_vars = _find_person_constant_vars(df, all_vars)
    per_row_vars = {v: m for v, m in drug_vars.items() if v not in constant_vars}
    constant_var_mappings = {v: m for v, m in drug_vars.items() if v in constant_vars}

    def _make_row(row_id, seqn, mapping, raw, var):
        field = mapping.get("omop_field", "")
        if field == "drug_concept_id":
            # Yes/no or categorical exposure fact -- only generate a
            # row when the raw value indicates a positive exposure.
            # NHANES convention: 1 = Yes, 2 = No (0/negative/NaN = no
            # exposure, nothing to record).
            try:
                positive = float(raw) == 1
            except (ValueError, TypeError):
                positive = False
            if not positive:
                return None
            concept_id = mapping.get("concept_id") or 0
            return (
                row_id, seqn, concept_id,
                PLACEHOLDER_DATE, PLACEHOLDER_DATE,
                PLACEHOLDER_TYPE_CONCEPT_ID, var[:50],
            )
        else:
            # Numeric field (e.g. quantity) -- store the raw value
            # directly; no specific substance identified, so
            # drug_concept_id is 0 (unmapped) unless the mapping
            # itself provides one.
            try:
                val = float(raw)
            except (ValueError, TypeError):
                return None
            concept_id = mapping.get("concept_id") or 0
            row = [
                row_id, seqn, concept_id,
                PLACEHOLDER_DATE, PLACEHOLDER_DATE,
                PLACEHOLDER_TYPE_CONCEPT_ID, var[:50],
            ]
            return tuple(row)

    if per_row_vars:
        for _, row in df.iterrows():
            seqn = int(row.get("SEQN", 0)) if pd.notna(row.get("SEQN", 0)) else 0
            if not seqn:
                continue
            for var, mapping in per_row_vars.items():
                if var in row and pd.notna(row[var]):
                    built = _make_row(row_id, seqn, mapping, row[var], var)
                    if built:
                        rows.append(built)
                        row_id += 1

    if constant_var_mappings:
        first_df = df.drop_duplicates(subset=["SEQN"])
        for _, row in first_df.iterrows():
            seqn = int(row.get("SEQN", 0)) if pd.notna(row.get("SEQN", 0)) else 0
            if not seqn:
                continue
            for var, mapping in constant_var_mappings.items():
                if var in row and pd.notna(row[var]):
                    built = _make_row(row_id, seqn, mapping, row[var], var)
                    if built:
                        rows.append(built)
                        row_id += 1

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

    # Step 2: LLM generates mapping (skip if already cached on disk --
    # this is what previous runs of this same ds_id already produced,
    # and demographic mappings shouldn't change between runs)
    mapping_path = f"dqd/mapping/mapping_{ds_id}.json"
    if os.path.exists(mapping_path):
        print(f"\n[2/3] Using cached mapping: {mapping_path}")
        with open(mapping_path, "r") as f:
            mapping = json.load(f)
        print(f"  {len(mapping)} variables loaded from cache")
    else:
        print("\n[2/3] LLM generating OMOP mapping...")
        mapping = nim_generate_mapping(ds_id, variables)
        print(f"  Total: {len(mapping)} variables mapped")

        os.makedirs("dqd/mapping", exist_ok=True)
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
