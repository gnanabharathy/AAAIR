"""
check_ptbxl_tables.py

Checks whether person/condition_occurrence/note tables have ANY rows
that could plausibly be from PTB-XL, to confirm whether etl_ptbxl_v2.py
was ever actually run (vs. only an earlier v1 script that didn't
populate these tables). This determines whether it's safe to just run
v2 now, or whether existing measurement/observation rows from a prior
run need to be cleared first to avoid duplicates.
"""

import psycopg2

conn = psycopg2.connect(host='localhost', port=5433, dbname='omop',
                         user='omop_user', password='omop_pass')
cur = conn.cursor()

# Does the person table have rows in/near the range we found earlier,
# and do they have person_source_value populated (patient_id)?
cur.execute("""
    SELECT COUNT(*), COUNT(person_source_value), COUNT(gender_source_value)
    FROM person
    WHERE person_id BETWEEN 142311 AND 161179
""")
print("person table in range 142311-161179:", cur.fetchone())

cur.execute("SELECT COUNT(*) FROM person")
print("total person rows in DB:", cur.fetchone()[0])

# condition_occurrence -- any rows referencing person_ids in that range?
cur.execute("""
    SELECT COUNT(*) FROM condition_occurrence
    WHERE person_id BETWEEN 142311 AND 161179
""")
print("condition_occurrence rows in that person_id range:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM condition_occurrence")
print("total condition_occurrence rows in DB:", cur.fetchone()[0])

# note -- any rows referencing person_ids in that range?
cur.execute("""
    SELECT COUNT(*) FROM note
    WHERE person_id BETWEEN 142311 AND 161179
""")
print("note rows in that person_id range:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM note")
print("total note rows in DB:", cur.fetchone()[0])

cur.close()
conn.close()
