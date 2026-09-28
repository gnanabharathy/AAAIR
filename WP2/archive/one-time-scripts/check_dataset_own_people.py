"""
check_dataset_own_people.py

Corrected version of check_shared_variable_values.py's sampling logic:
instead of picking ARBITRARY people who happen to have a given
variable recorded anywhere in the observation table (which can pick up
people who don't even belong to the dataset being investigated -- as
happened with dr1iff_e-2007 and person_id=21005, who isn't in that
file at all), this picks people from THIS DATASET'S OWN real SEQN list.

Usage: python3 check_dataset_own_people.py <ds_id> <variable_name> <n_people>
"""

import json
import os
import sys
import urllib.request

import psycopg2
import pyreadstat

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "omop",
    "user": "omop_user",
    "password": "omop_pass",
}


def download_xpt_if_needed(ds_id, entry):
    xpt_path = f"/tmp/{ds_id}.xpt"
    if os.path.exists(xpt_path):
        return xpt_path
    doc_url = entry["url"]
    xpt_url = doc_url.replace(".htm", ".xpt").replace(".html", ".xpt")
    req = urllib.request.Request(xpt_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(xpt_path, "wb") as f:
            f.write(r.read())
    return xpt_path


def main():
    ds_id = sys.argv[1]
    var_name = sys.argv[2]
    n_people = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    schema = json.load(open("schema.json"))
    entry = schema[ds_id]
    xpt_path = download_xpt_if_needed(ds_id, entry)
    df, _ = pyreadstat.read_xport(xpt_path, encoding="latin1")
    seqns = sorted(int(s) for s in df["SEQN"].dropna().unique())[:n_people]

    print(f"Checking '{var_name}' for {len(seqns)} people who ARE actually "
          f"in {ds_id}'s own SEQN list: {seqns}\n")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    for pid in seqns:
        cur.execute(
            "SELECT observation_id, value_as_number, value_as_string "
            "FROM public.observation "
            "WHERE person_id = %s AND observation_source_value = %s "
            "ORDER BY observation_id",
            (pid, var_name),
        )
        rows = cur.fetchall()
        print(f"person_id={pid}: {len(rows)} row(s)")
        for obs_id, val_num, val_str in rows:
            print(f"    observation_id={obs_id}  value_as_number={val_num}  value_as_string={val_str}")
        print()

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
