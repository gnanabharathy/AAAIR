"""
reverify_24_structural.py

Re-verifies, dataset by dataset, whether each of the 24
"structural_not_applicable" dietary datasets genuinely lacks a SEQN
column (confirming they can't map to person/measurement/observation),
rather than relying on the earlier one-time classification. Prints
each dataset's actual column list directly from its .xpt file.

Usage: python3 reverify_24_structural.py
"""

import json
import os
import urllib.request

import pyreadstat

STRUCTURAL_24 = [
    "nhanes-dietary-drxfcd_c-2003", "nhanes-dietary-drxfcd_d-2005",
    "nhanes-dietary-drxfcd_e-2007", "nhanes-dietary-drxfcd_f-2009",
    "nhanes-dietary-drxfcd_g-2011", "nhanes-dietary-drxfcd_h-2013",
    "nhanes-dietary-drxfcd_i-2015", "nhanes-dietary-drxfcd_j-2017",
    "nhanes-dietary-drxfcd_l-2021", "nhanes-dietary-drxfmt-1999",
    "nhanes-dietary-drxfmt_b-2001", "nhanes-dietary-drxmcd_c-2003",
    "nhanes-dietary-drxmcd_d-2005", "nhanes-dietary-drxmcd_e-2007",
    "nhanes-dietary-drxmcd_f-2009", "nhanes-dietary-drxmcd_g-2011",
    "nhanes-dietary-dsbi-1999", "nhanes-dietary-dsii-1999",
    "nhanes-dietary-dspi-1999", "nhanes-dietary-foodlk_c-2003",
    "nhanes-dietary-foodlk_d-2005", "nhanes-dietary-p_drxfcd-2017",
    "nhanes-dietary-varlk_c-2003", "nhanes-dietary-varlk_d-2005",
]


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


schema = json.load(open("schema.json"))

has_seqn = []
no_seqn = []
error = []

for ds_id in STRUCTURAL_24:
    entry = schema.get(ds_id)
    if not entry:
        error.append((ds_id, "not in schema.json"))
        continue
    try:
        xpt_path = download_xpt_if_needed(ds_id, entry)
        _, meta = pyreadstat.read_xport(xpt_path, encoding="latin1", metadataonly=True)
        columns = list(meta.column_names)
        if "SEQN" in columns:
            has_seqn.append((ds_id, columns))
        else:
            no_seqn.append((ds_id, columns))
    except Exception as e:
        error.append((ds_id, str(e)))

print(f"{'='*60}\nDatasets confirmed WITHOUT SEQN (genuinely structural): {len(no_seqn)}\n{'='*60}")
for ds_id, cols in no_seqn:
    print(f"  {ds_id}: {cols}")

print(f"\n{'='*60}\nDatasets that DO have SEQN (need re-review!): {len(has_seqn)}\n{'='*60}")
for ds_id, cols in has_seqn:
    print(f"  {ds_id}: {cols}")

print(f"\n{'='*60}\nErrors: {len(error)}\n{'='*60}")
for ds_id, err in error:
    print(f"  {ds_id}: {err}")
