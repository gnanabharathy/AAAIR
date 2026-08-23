#!/usr/bin/env python3
"""
extractor_phidu.py — Extract PHIDU dataset metadata into schema.json
Each sheet in each xlsx file becomes one dataset entry.

Usage:
    python3 extractor_phidu.py --category "PHA by location"
    python3 extractor_phidu.py --category "PHA by topic"
    python3 extractor_phidu.py --category "LGA"
    python3 extractor_phidu.py --category "PHN"
    python3 extractor_phidu.py --category "Socioeconomic"
    python3 extractor_phidu.py --category "Remoteness"
    python3 extractor_phidu.py --category "ATSI"
    python3 extractor_phidu.py --category "Indigenous Comparison"
"""

import os, sys, json, re, time, urllib.request, argparse
import pandas as pd

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
for line in open(".env").read().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

NIM_API_KEY  = os.getenv("NIM_API_KEY", "")
NIM_MODEL    = os.getenv("NIM_MODEL", "")
NIM_BASE_URL = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

SCHEMA_FILE = "schema.json"
TMP_DIR = "/tmp/phidu"
os.makedirs(TMP_DIR, exist_ok=True)

SKIP_SHEETS = {
    "Front_page", "Topics", "Contents", "Key", "Notes",
    "front_page", "topics", "contents", "key", "notes",
}

# One representative file per category
TEST_FILES = [
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_aust.xlsx",
        "source": "phidu-pha-aust",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "Australia",
        "category": "PHA by location",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_nsw.xlsx",
        "source": "phidu-pha-nsw",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "NSW",
        "category": "PHA by location",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_vic.xlsx",
        "source": "phidu-pha-vic",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "Vic",
        "category": "PHA by location",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_qld.xlsx",
        "source": "phidu-pha-qld",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "Qld",
        "category": "PHA by location",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_sa.xlsx",
        "source": "phidu-pha-sa",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "SA",
        "category": "PHA by location",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_wa.xlsx",
        "source": "phidu-pha-wa",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "WA",
        "category": "PHA by location",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_tas.xlsx",
        "source": "phidu-pha-tas",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "Tas",
        "category": "PHA by location",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_nt.xlsx",
        "source": "phidu-pha-nt",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "NT",
        "category": "PHA by location",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_act.xlsx",
        "source": "phidu-pha-act",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "ACT",
        "category": "PHA by location",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_health_status_aust.xlsx",
        "source": "phidu-pha-health-status",
        "geo": "Population Health Area",
        "subtype": "health-status",
        "region": "Australia",
        "category": "PHA by topic",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_use_provision_health_aust.xlsx",
        "source": "phidu-pha-health-services",
        "geo": "Population Health Area",
        "subtype": "health-services",
        "region": "Australia",
        "category": "PHA by topic",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_demographic_social_aust.xlsx",
        "source": "phidu-pha-demographics",
        "geo": "Population Health Area",
        "subtype": "social-determinants",
        "region": "Australia",
        "category": "PHA by topic",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/lga/phidu_data_lga_aust.xlsx",
        "source": "phidu-lga-aust",
        "geo": "Local Government Area",
        "subtype": "health-status",
        "region": "Australia",
        "category": "LGA",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/phn_pha_parts/phidu_data_phn_pha_parts_aust.xlsx",
        "source": "phidu-phn-pha",
        "geo": "Primary Health Network",
        "subtype": "health-services",
        "region": "Australia",
        "category": "PHN",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/quintiles/phidu_data_quintiles_aust.xlsx",
        "source": "phidu-quintiles",
        "geo": "Socioeconomic Disadvantage",
        "subtype": "social-determinants",
        "region": "Australia",
        "category": "Socioeconomic",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-aust/remoteness/phidu_data_remoteness_aust.xlsx",
        "source": "phidu-remoteness",
        "geo": "Remoteness Area",
        "subtype": "social-determinants",
        "region": "Australia",
        "category": "Remoteness",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/atsi-sha/phidu_atsi_data_ia_aust.xlsx",
        "source": "phidu-atsi-ia",
        "geo": "Indigenous Area",
        "subtype": "indigenous-health",
        "region": "Australia",
        "category": "ATSI",
    },
    {
        "url": "https://phidu.torrens.edu.au/current/data/sha-topics/Indigenous-status-comparison/phidu_Indigenous_status_comparison_data_ia_aust.xlsx",
        "source": "phidu-indigenous-comparison-ia",
        "geo": "Indigenous Area",
        "subtype": "indigenous-health",
        "region": "Australia",
        "category": "Indigenous Comparison",
    },
]

# ---------------------------------------------------------------------------
# NIM helpers
# ---------------------------------------------------------------------------

def nim_chat(messages, max_tokens=1000, retries=3):
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
                text = msg.get("content") or msg.get("reasoning_content") or ""
                # Extract last clean sentence from reasoning output
                if text and not msg.get("content"):
                    sentences = [s.strip() for s in text.split('.') if s.strip() and len(s.strip()) > 20 and not s.strip().startswith('We need') and not s.strip().startswith('Let') and not s.strip().startswith('Maybe')]
                    text = sentences[-1] + '.' if sentences else text[:200]
                return text
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
    except:
        for ch in ('[', '{'):
            i = text.find(ch)
            if i != -1:
                try: return json.loads(text[i:])
                except: pass
    return default

# ---------------------------------------------------------------------------
# Extract column names from a sheet
# ---------------------------------------------------------------------------

def get_sheet_columns(path, sheet_name):
    try:
        df_header = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=5)
        col_names = []
        for val in df_header.iloc[0]:
            if pd.notna(val) and not str(val).startswith("Unnamed"):
                name = str(val).strip()
                skip_vals = {"BACK TO CONTENTS", "Link to Notes on the Data",
                             "Link to SA2 to PHA list", "Link to Statistical Areas Level 3 / Level 4 totals",
                             "Link to Key", "Link to State/ Territory and Australian totals"}
                if name and name not in skip_vals:
                    col_names.append(name)
        return col_names
    except Exception as e:
        return []

# ---------------------------------------------------------------------------
# LLM generates metadata for one sheet
# ---------------------------------------------------------------------------

def llm_generate_metadata(sheet_name, col_names, file_info):
    col_str = ", ".join(col_names[:15]) if col_names else "not available"
    prompt = f"""Generate metadata for this Australian health dataset.

Dataset: {sheet_name.replace('_', ' ')}
Source: PHIDU Social Health Atlas of Australia
Geography: {file_info['geo']} ({file_info['region']})
Category: {file_info['category']}
Columns/Indicators: {col_str}

Return ONLY a JSON object with these fields:
{{
  "name": "short descriptive name (max 80 chars)",
  "desc": "one sentence description of what this dataset contains",
  "tasks": ["list", "of", "applicable", "ML", "tasks", "from: classification, regression, clustering, time-series"]
}}"""

    reply = nim_chat([
        {"role": "system", "content": "You are a health data expert. Return ONLY valid JSON, no markdown."},
        {"role": "user", "content": prompt},
    ])
    return safe_json(reply, default={
        "name": sheet_name.replace("_", " ").title(),
        "desc": f"PHIDU {file_info['category']} data for {file_info['geo']}",
        "tasks": ["regression", "classification"],
    })

# ---------------------------------------------------------------------------
# Download file
# ---------------------------------------------------------------------------

def download_file(url, filename):
    path = os.path.join(TMP_DIR, filename)
    if os.path.exists(path):
        print(f"  Already downloaded: {filename}")
        return path
    print(f"  Downloading {filename}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(path, "wb") as f:
            f.write(r.read())
    print(f"  Saved: {filename}")
    return path

# ---------------------------------------------------------------------------
# Process one file
# ---------------------------------------------------------------------------

def process_file(file_info, schema):
    url = file_info["url"]
    filename = url.split("/")[-1]
    source = file_info["source"]

    print(f"\n{'='*60}")
    print(f"Category: {file_info['category']}")
    print(f"File: {filename}")
    print(f"{'='*60}")

    path = download_file(url, filename)
    xl = pd.ExcelFile(path)
    data_sheets = [s for s in xl.sheet_names if s not in SKIP_SHEETS]
    print(f"  {len(data_sheets)} data sheets found")

    added = 0
    for i, sheet in enumerate(data_sheets, 1):
        name_clean = re.sub(r"[^a-z0-9]+", "-", sheet.lower()).strip("-")
        ds_id = f"{source}-{name_clean}"

        if ds_id in schema:
            print(f"  [{i}/{len(data_sheets)}] SKIP: {ds_id}")
            continue

        print(f"  [{i}/{len(data_sheets)}] Processing: {sheet}")

        col_names = get_sheet_columns(path, sheet)

        try:
            meta = llm_generate_metadata(sheet, col_names, file_info)
            time.sleep(5)
        except Exception as e:
            print(f"    LLM failed: {e}, using defaults")
            meta = {
                "name": sheet.replace("_", " ").title(),
                "desc": f"PHIDU {file_info['category']} data — {file_info['geo']}",
                "tasks": ["regression", "classification"],
            }

        schema[ds_id] = {
            "name": meta.get("name", sheet.replace("_", " ").title()),
            "desc": meta.get("desc", ""),
            "source": "PHIDU",
            "subtypes": [file_info["subtype"]],
            "tasks": meta.get("tasks", ["regression"]),
            "url": url,
            "sheet": sheet,
            "geo": file_info["geo"],
            "region": file_info["region"],
            "last_updated": "2026",
            "variable_count": len(col_names),
            "variables": [{"name": c, "label": c, "data_type": "Continuous"} for c in col_names],
        }
        added += 1
        print(f"    Added: {ds_id}")

        # Save after each sheet
        with open(SCHEMA_FILE, "w") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"\n  Done: {added} new datasets added from {filename}")
    return added

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", help="Category to process (e.g. 'PHA by location')", required=True)
    args = parser.parse_args()

    if os.path.exists(SCHEMA_FILE):
        schema = json.load(open(SCHEMA_FILE))
        print(f"Loaded schema.json ({len(schema)} existing datasets)")
    else:
        schema = {}
        print("Creating new schema.json")

    files = [f for f in TEST_FILES if f["category"] == args.category]
    if not files:
        print(f"Unknown category: {args.category}")
        print("Available categories:")
        for f in TEST_FILES:
            print(f"  {f['category']}")
        sys.exit(1)

    total_added = 0
    for file_info in files:
        total_added += process_file(file_info, schema)

    print(f"\n{'='*60}")
    print(f"DONE: {total_added} new datasets added")
    print(f"Total in schema.json: {len(schema)}")

if __name__ == "__main__":
    main()
