import psycopg2

conn = psycopg2.connect(host='localhost', port=5433, dbname='omop',
                         user='omop_user', password='omop_pass')
cur = conn.cursor()

print("--- Corrected check: nurse/site/device/validated_by ---")
for field in ['nurse', 'site', 'device', 'validated_by']:
    cur.execute(
        "SELECT COUNT(*), COUNT(DISTINCT person_id) FROM observation "
        "WHERE observation_source_value LIKE %s",
        (f"{field}:%",)
    )
    count, distinct_people = cur.fetchone()
    print(f"  {field}: {count} rows, {distinct_people} distinct people")

print("\n--- extra_beats check ---")
cur.execute(
    "SELECT COUNT(*) FROM measurement WHERE measurement_source_value = 'extra_beats'"
)
print(f"  measurement rows with source_value='extra_beats': {cur.fetchone()[0]}")
cur.execute(
    "SELECT COUNT(*) FROM observation WHERE observation_source_value = 'extra_beats'"
)
print(f"  observation rows with source_value='extra_beats': {cur.fetchone()[0]}")

cur.close()
conn.close()
