"""
check_ptbxl_full.py

Checks the full picture of what actually landed in measurement/observation
for PTBXL_ecg_records: which of its 28 schema.json variables have any
rows at all, and confirms the person_id range doesn't overlap with any
other dataset's registered rows (to make sure backfilling by person_id
range alone would be safe, without needing variable-name filtering).
"""

import json
import psycopg2

conn = psycopg2.connect(host='localhost', port=5433, dbname='omop',
                         user='omop_user', password='omop_pass')
cur = conn.cursor()

schema = json.load(open('schema.json'))
var_names = [v['name'] for v in schema['PTBXL_ecg_records'].get('variables', [])]

print(f"Checking all {len(var_names)} PTB-XL variables against measurement/observation...\n")

cur.execute("""
    SELECT measurement_source_value, COUNT(*), COUNT(DISTINCT person_id)
    FROM measurement
    WHERE measurement_source_value = ANY(%s)
    GROUP BY measurement_source_value
    ORDER BY measurement_source_value
""", (var_names,))
print("measurement table matches:")
found_in_measurement = set()
for row in cur.fetchall():
    print(" ", row)
    found_in_measurement.add(row[0])

cur.execute("""
    SELECT observation_source_value, COUNT(*), COUNT(DISTINCT person_id)
    FROM observation
    WHERE observation_source_value = ANY(%s)
    GROUP BY observation_source_value
    ORDER BY observation_source_value
""", (var_names,))
print("\nobservation table matches:")
found_in_observation = set()
for row in cur.fetchall():
    print(" ", row)
    found_in_observation.add(row[0])

missing = set(var_names) - found_in_measurement - found_in_observation
print(f"\nVariables from schema.json NOT found in either table ({len(missing)}):")
for v in sorted(missing):
    print(" ", v)

# Check person_id range overlap with any OTHER registered dataset
cur.execute("""
    SELECT MIN(person_id), MAX(person_id)
    FROM measurement
    WHERE measurement_source_value IN ('age','height','weight')
""")
lo, hi = cur.fetchone()
print(f"\nPTB-XL person_id range (from age/height/weight rows): {lo} - {hi}")

cur.execute("""
    SELECT DISTINCT drr.ds_id
    FROM dataset_row_registry drr
    JOIN measurement m ON m.measurement_id = drr.row_id AND drr.table_name = 'measurement'
    WHERE m.person_id BETWEEN %s AND %s
""", (lo, hi))
overlapping = cur.fetchall()
print(f"Other datasets already registered with person_id in this range: {overlapping}")

cur.close()
conn.close()
