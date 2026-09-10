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
        [python_bin, "etl_v3.py", ds_id],
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

    # Generate an isolated view schema scoped to just this dataset's rows
    # (see generate_dataset_view_schema.py), so DQD checks this dataset
    # alone instead of the whole cumulative public schema.
    log(f"  [DQD] Generating isolated view schema for {ds_id}")
    project_dir = os.path.dirname(os.path.abspath(__file__))
    python_bin = os.path.join(project_dir, "venv", "bin", "python3.11")
    view_result = subprocess.run(
        [python_bin, "generate_dataset_view_schema.py", ds_id],
        capture_output=True, text=True, timeout=300,
        cwd=project_dir,
    )
    if view_result.returncode != 0:
        log(f"  [DQD] View schema generation FAILED for {ds_id} -- "
            f"likely no dataset_row_registry entries (dataset predates "
            f"the registry, or was ETL'd with an older etl_v2.py).")
        log(f"  STDOUT: {view_result.stdout[-500:]}")
        log(f"  STDERR: {view_result.stderr[-500:]}")
        raise RuntimeError(f"View schema generation failed for {ds_id}")

    # Parse the generated schema name from the script's stdout
    schema_match = re.search(r"Created schema '([^']+)'", view_result.stdout)
    if not schema_match:
        raise RuntimeError(
            f"Could not parse generated schema name from view-generation "
            f"output for {ds_id}. Output was:\n{view_result.stdout}"
        )
    view_schema = schema_match.group(1)
    log(f"  [DQD] View schema ready: {view_schema}")

    log(f"  [DQD] Starting {ds_id}")
    # Stream Rscript's output live to the terminal (line by line) instead
    # of buffering it all until the process exits -- capture_output=True
    # was hiding all of DQD's "Processing check description: ..." progress
    # lines until the whole run finished, which made it impossible to
    # tell a slow-but-healthy run apart from a stuck one.
    output_lines = []
    process = subprocess.Popen(
        ["Rscript", "dqd.R", ds_id, cdm_source_name, view_schema],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in process.stdout:
        print(line, end="")
        output_lines.append(line)
    process.wait(timeout=7200)
    full_output = "".join(output_lines)

    if process.returncode != 0:
        log(f"  [DQD] FAILED: {ds_id}")
        log(f"  OUTPUT: {full_output[-1000:]}")
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
def process_one(ds_id, schema, progress, skip_etl=False):
    if ds_id in progress["done"]:
        log(f"[SKIP] Already done: {ds_id}")
        return True

    log(f"\n{'='*60}")
    log(f"Processing: {ds_id}")
    log(f"{'='*60}")

    try:
        if skip_etl:
            log(f"  [ETL] Skipped (--skip-etl): assuming data already in "
                f"measurement/observation and dataset_row_registry from a prior run")
        else:
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
    parser.add_argument("--skip-etl", action="store_true",
                         help="Skip re-running ETL; assumes data is already in "
                              "measurement/observation and dataset_row_registry "
                              "from a prior successful run. Goes straight to "
                              "view generation + DQD.")
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
        if process_one(ds_id, schema, progress, skip_etl=args.skip_etl):
            ok += 1
        else:
            fail += 1

    log(f"\n{'='*60}")
    log(f"BATCH COMPLETE: {ok} OK, {fail} failed")
    log(f"Failed IDs saved in {PROGRESS_FILE}")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()
