"""
verify_dietary_completion.py

Final verification for the dietary category's isolated DQD work:
  1. Confirms all 101 real person-centric datasets have a report file
     in dqd/raw/.
  2. Confirms the 24 structural (reference-table) datasets correctly
     have NO report (since they were never meant to get one).
  3. For each of the 101, cross-checks the report's PERSON/MEASUREMENT/
     OBSERVATION/DRUG_EXPOSURE denominators against the dataset's own
     dataset_row_registry + shared_row_registry counts, to catch the
     "file exists but reflects stale/wrong data" failure mode (as
     happened with demo-1999 before its registry was fixed).

Usage: python3 verify_dietary_completion.py
"""

import json
import os

import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}

TABLE_ID_COLUMNS = {
    "person": "PERSON",
    "measurement": "MEASUREMENT",
    "observation": "OBSERVATION",
    "drug_exposure": "DRUG_EXPOSURE",
}

classification = json.load(open("backfill_classification.json"))
ok_ids = sorted(classification["ok"])
structural_ids = sorted(classification["structural_not_applicable"])

print(f"Expected: {len(ok_ids)} person-centric datasets with reports, "
      f"{len(structural_ids)} structural datasets with NO report.\n")

# --- Check 1: report file existence ---
missing_reports = [d for d in ok_ids if not os.path.exists(f"dqd/raw/{d}.json")]
unexpected_reports = [d for d in structural_ids if os.path.exists(f"dqd/raw/{d}.json")]

print(f"{'='*60}\nCheck 1: report file existence\n{'='*60}")
print(f"Person-centric datasets MISSING a report: {len(missing_reports)}")
for d in missing_reports:
    print(f"  {d}")
print(f"Structural datasets that unexpectedly HAVE a report: {len(unexpected_reports)}")
for d in unexpected_reports:
    print(f"  {d}")

# --- Check 2: registry-vs-report denominator cross-check ---
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

mismatches = []
checked = 0

for ds_id in ok_ids:
    report_path = f"dqd/raw/{ds_id}.json"
    if not os.path.exists(report_path):
        continue

    cur.execute(
        "SELECT table_name, COUNT(*) FROM ("
        "  SELECT table_name, row_id FROM dataset_row_registry WHERE ds_id = %s"
        "  UNION"
        "  SELECT table_name, row_id FROM shared_row_registry WHERE ds_id = %s"
        ") combined GROUP BY table_name",
        (ds_id, ds_id),
    )
    registry_counts = dict(cur.fetchall())

    report = json.load(open(report_path))
    results = report.get("CheckResults", [])

    report_counts = {}
    for r in results:
        if r.get("checkName") == "isRequired":
            table = r.get("cdmTableName")
            denom = r.get("numDenominatorRows")
            if table and denom:
                report_counts[table.lower()] = denom

    checked += 1
    for table, reg_count in registry_counts.items():
        report_count = report_counts.get(table)
        if report_count is not None and report_count != reg_count:
            mismatches.append((ds_id, table, reg_count, report_count))

print(f"\n{'='*60}\nCheck 2: registry vs report denominator cross-check "
      f"({checked} datasets checked)\n{'='*60}")
print(f"Mismatches found: {len(mismatches)}")
for ds_id, table, reg, rep in mismatches:
    print(f"  {ds_id} / {table}: registry={reg}, report={rep}")

cur.close()
conn.close()

print(f"\n{'='*60}\nSummary\n{'='*60}")
if not missing_reports and not unexpected_reports and not mismatches:
    print("ALL CHECKS PASSED: 101 reports present and consistent, "
          "24 structural datasets correctly have none.")
else:
    print("ISSUES FOUND -- see details above.")
