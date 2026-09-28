import psycopg2
conn = psycopg2.connect(host='localhost', port=5433, dbname='omop', user='omop_user', password='omop_pass')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM public.cdm_source")
print("public.cdm_source row count:", cur.fetchone()[0])
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'dqd_view_ptbxl_ecg_records'
    ORDER BY table_name
""")
print("Tables/views inside the isolated schema:")
for row in cur.fetchall():
    print(" ", row[0])
