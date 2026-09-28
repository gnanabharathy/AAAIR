import psycopg2
conn = psycopg2.connect(host='localhost', port=5433, dbname='omop', user='omop_user', password='omop_pass')
cur = conn.cursor()

cur.execute("""
    SELECT measurement_source_value, COUNT(*), COUNT(DISTINCT person_id)
    FROM measurement
    WHERE measurement_source_value IN ('ecg_id','patient_id','age','sex','height','weight','device')
    GROUP BY measurement_source_value
""")
print("measurement table:")
for row in cur.fetchall():
    print(" ", row)

cur.execute("""
    SELECT observation_source_value, COUNT(*), COUNT(DISTINCT person_id)
    FROM observation
    WHERE observation_source_value IN ('ecg_id','patient_id','age','sex','height','weight','device')
    GROUP BY observation_source_value
""")
print("observation table:")
for row in cur.fetchall():
    print(" ", row)

cur.execute("SELECT MIN(person_id), MAX(person_id), COUNT(DISTINCT person_id) FROM measurement WHERE measurement_source_value = 'age'")
print("person_id range for 'age' rows:", cur.fetchone())
