import psycopg2
conn = psycopg2.connect(host='localhost', port=5433, dbname='omop', user='omop_user', password='omop_pass')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM observation WHERE observation_source_value = 'extra_beats'")
print('extra_beats rows now:', cur.fetchone()[0])
