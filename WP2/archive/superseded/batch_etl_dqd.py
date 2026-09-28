#!/usr/bin/env python3
"""
batch_etl_dqd.py 
Usage:
    python3 batch_etl_dqd.py --category demographics
    python3 batch_etl_dqd.py --category dietary
    python3 batch_etl_dqd.py --ids nhanes-demographics-demo_i-2015 nhanes-demographics-demo_j-2017
"""

import os, sys, json, re, subprocess, argparse, traceback, glob, shutil
from datetime import datetime

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
for line in open(".env").read().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

LOG_FILE = "batch_errors.log"
PROGRESS_FILE = "batch_progress.json"
RAW_DIR = "dqd/raw"
RESULTS_DIR = "dqd/results"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        return json.load(open(PROGRESS_FILE))
    return {"done": [], "failed": []}

def save_progress(progress):
    json.dump(progress, open(PROGRESS_FILE, "w"), indent=2)

# ---------------------------------------------------------------------------
# Get dataset IDs by category
# ---------------------------------------------------------------------------
def get_ids_by_category(schema, category):
    ids = []
    for ds_id, entry in schema.items():
        subtypes = entry.get("subtypes", [])
        if category.lower() in [s.lower() for s in subtypes]:
            ids.append(ds_id)
    return sorted(ids)

# ---------------------------------------------------------------------------
# Run ETL for one dataset
# ---------------------------------------------------------------------------
def run_etl(ds_id):
    log(f"  [ETL] Starting {ds_id}")
    project_dir = os.path.dirname(os.path.abspath(__file__))
    python_bin = os.path.join(project_dir, "venv", "bin", "python3.11")
    result = subprocess.run(
        [python_bin, "etl_v2.py", ds_id],
        capture_output=True, text=True, timeout=7200,
        cwd=project_dir
    )
    if result.returncode != 0:
        log(f"  [ETL] FAILED: {ds_id}")
        log(f"  STDOUT: {result.stdout[-500:]}")
        log(f"  STDERR: {result.stderr[-500:]}")
        raise RuntimeError(f"ETL failed for {ds_id}")
    log(f"  [ETL] Done: {ds_id}")

# ---------------------------------------------------------------------------
# Run DQD for one dataset
# ---------------------------------------------------------------------------
def run_dqd(ds_id, schema_entry):
    # Build a human-readable CDM source name from schema entry
    cdm_source_name = schema_entry.get("name", ds_id)[:100]  # max 100 chars

    output_path = os.path.join(RAW_DIR, f"{ds_id}.json")
    if os.path.exists(output_path):
        log(f"  [DQD] Already exists, skipping: {output_path}")
        return

    log(f"  [DQD] Starting {ds_id}")
    result = subprocess.run(
        ["Rscript", "dqd.R", ds_id, cdm_source_name],
        capture_output=True, text=True, timeout=7200  # 30 min timeout
    )
    if result.returncode != 0:
        log(f"  [DQD] FAILED: {ds_id}")
        log(f"  STDOUT: {result.stdout[-500:]}")
        log(f"  STDERR: {result.stderr[-500:]}")
        raise RuntimeError(f"DQD failed for {ds_id}")
    
    if not os.path.exists(output_path):
        raise RuntimeError(f"DQD ran but output not found: {output_path}")
    
    log(f"  [DQD] Done: {output_path}")

    log_pattern = os.path.join(RAW_DIR, f"log_DqDashboard_{cdm_source_name}.txt")
    matches = glob.glob(log_pattern)
    if matches:
        for log_src in matches:
            log_dest = os.path.join(RESULTS_DIR, os.path.basename(log_src))
            shutil.move(log_src, log_dest)
            log(f"  [DQD] Log moved to: {log_dest}")
    else:
        log(f"  [DQD] WARNING: no log file found matching {log_pattern}")

# ---------------------------------------------------------------------------
# Process one dataset
# ---------------------------------------------------------------------------
def process_one(ds_id, schema, progress):
    if ds_id in progress["done"]:
        log(f"[SKIP] Already done: {ds_id}")
        return True

    log(f"\n{'='*60}")
    log(f"Processing: {ds_id}")
    log(f"{'='*60}")

    try:
        run_etl(ds_id)
        run_dqd(ds_id, schema[ds_id])
        progress["done"].append(ds_id)
        # Remove from failed if it was there before
        if ds_id in progress["failed"]:
            progress["failed"].remove(ds_id)
        save_progress(progress)
        log(f"[OK] {ds_id}")
        return True
    except Exception as e:
        log(f"[FAIL] {ds_id}: {e}")
        traceback.print_exc()
        if ds_id not in progress["failed"]:
            progress["failed"].append(ds_id)
        save_progress(progress)
        return False

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", help="Category to process (e.g. demographics)")
    parser.add_argument("--ids", nargs="+", help="Specific dataset IDs to process")
    parser.add_argument("--retry-failed", action="store_true", help="Retry previously failed datasets")
    args = parser.parse_args()

    schema = json.load(open("schema.json"))
    progress = load_progress()

    if args.retry_failed:
        ids = list(progress["failed"])
        log(f"Retrying {len(ids)} failed datasets")
    elif args.ids:
        ids = args.ids
    elif args.category:
        ids = get_ids_by_category(schema, args.category)
        log(f"Found {len(ids)} datasets in category '{args.category}'")
    else:
        print("Usage: python3 batch_etl_dqd.py --category demographics")
        print("       python3 batch_etl_dqd.py --ids <id1> <id2>")
        print("       python3 batch_etl_dqd.py --retry-failed")
        sys.exit(1)

    # Filter out missing datasets
    ids = [i for i in ids if i in schema]
    
    total = len(ids)
    done_count = sum(1 for i in ids if i in progress["done"])
    log(f"Total: {total}, Already done: {done_count}, Remaining: {total - done_count}")

    ok, fail = 0, 0
    for n, ds_id in enumerate(ids, 1):
        log(f"\n--- [{n}/{total}] ---")
        if process_one(ds_id, schema, progress):
            ok += 1
        else:
            fail += 1

    log(f"\n{'='*60}")
    log(f"BATCH COMPLETE: {ok} OK, {fail} failed")
    log(f"Failed IDs saved in {PROGRESS_FILE}")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()
