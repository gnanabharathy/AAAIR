import psycopg2
conn = psycopg2.connect(host='localhost', port=5433, dbname='omop', user='omop_user', password='omop_pass')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM dataset_row_registry WHERE ds_id = 'PTBXL_ecg_records'")
print('registry rows:', cur.fetchone()[0])
