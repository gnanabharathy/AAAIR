import psycopg2
conn = psycopg2.connect(host='localhost', port=5433, dbname='omop', user='omop_user', password='omop_pass')
conn.autocommit = True
cur = conn.cursor()
cur.execute('ALTER SCHEMA "dqd_view_PTBXL_ecg_records" RENAME TO dqd_view_ptbxl_ecg_records')
print("Schema renamed successfully.")
