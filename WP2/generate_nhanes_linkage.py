"""
generate_nhanes_linkage.py

Generates a "linkage" field for every NHANES entry in data.js, following
a deterministic rule (not hand-written per dataset):

  - Every NHANES dataset shares the participant identifier SEQN with
    every other NHANES dataset from the SAME two-year survey cycle.
  - The cycle's demographics file is the conventional anchor -- NHANES
    analysis guidance is to merge every other file to demographics via
    SEQN before combining across files.
  - The 24 dietary reference/lookup tables (no SEQN -- see DQD.md) get
    a distinct, honest note instead: they aren't person-linkable, and
    are referenced by food/ingredient code values from the dietary
    interview and supplement files, not by SEQN.

This does NOT hand-author a sentence per dataset -- it derives the
cycle year and demographics anchor from data.js's own id/name/docUrl
fields, so it stays correct automatically as new NHANES datasets are
added.

Usage: python3 generate_nhanes_linkage.py
Writes the patched data.js in place (after printing a preview and
diff-style summary). Makes a timestamped backup first.
"""

import json
import re
import shutil
from datetime import datetime

STRUCTURAL_NOT_APPLICABLE = {
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
}

STRUCTURAL_LINKAGE_NOTE = (
    "No SEQN column -- not person-linkable. Referenced by food/ingredient "
    "code values from the dietary interview and supplement files for the "
    "same cycle."
)


def extract_cycle_year(entry):
    """Pull the 4-digit cycle start year from docUrl (most reliable),
    falling back to the id's trailing year segment."""
    m = re.search(r'/Public/(\d{4})/', entry.get('docUrl', ''))
    if m:
        return m.group(1)
    m = re.search(r'-(\d{4})$', entry['id'])
    return m.group(1) if m else None


def extract_cycle_range(entry):
    """Pull the '2005-06'-style display range from the name field."""
    m = re.search(r'\((\d{4}-\d{2})\)', entry.get('name', ''))
    return m.group(1) if m else entry.get('id', '')[-4:]


def extract_file_code(entry):
    """Pull the file code (e.g. 'DEMO_D') from the name field."""
    m = re.search(r'—\s*(\S+)\s*\(', entry.get('name', ''))
    return m.group(1) if m else entry['id']


def main():
    with open('data.js', 'r', encoding='utf-8') as f:
        content = f.read()

    m = re.search(r'const DATASETS = (\[.*?\]);', content, re.DOTALL)
    if not m:
        print("ERROR: could not find DATASETS array in data.js")
        return
    data = json.loads(m.group(1))

    nhanes = [d for d in data if d.get('source') == 'NHANES']
    print(f"Found {len(nhanes)} NHANES entries")

    # Build cycle-year -> demographics-entry lookup
    demo_by_year = {}
    for d in nhanes:
        if 'demographics' in d.get('subtypes', []):
            year = extract_cycle_year(d)
            if year:
                demo_by_year[year] = d

    print(f"Found demographics anchor for {len(demo_by_year)} cycles: "
          f"{sorted(demo_by_year.keys())}")

    missing_anchor_years = set()
    linkage_by_id = {}

    for d in nhanes:
        year = extract_cycle_year(d)
        cycle_range = extract_cycle_range(d)

        if d['id'] in STRUCTURAL_NOT_APPLICABLE:
            linkage_by_id[d['id']] = STRUCTURAL_LINKAGE_NOTE
            continue

        if year is None:
            continue  # can't determine cycle; leave unset rather than guess

        anchor = demo_by_year.get(year)

        if anchor and anchor['id'] == d['id']:
            linkage_by_id[d['id']] = (
                f"Core linking file for the NHANES {cycle_range} cycle -- "
                f"all other NHANES {cycle_range} datasets link to this file "
                f"via SEQN."
            )
        elif anchor:
            anchor_code = extract_file_code(anchor)
            linkage_by_id[d['id']] = (
                f"Links to {anchor_code} ({cycle_range} demographics) and "
                f"other NHANES {cycle_range} datasets via SEQN."
            )
        else:
            missing_anchor_years.add(year)
            linkage_by_id[d['id']] = (
                f"Links to other NHANES {cycle_range} datasets via SEQN "
                f"(demographics file for this cycle not found in schema)."
            )

    if missing_anchor_years:
        print(f"\nWARNING: no demographics anchor found for cycle years: "
              f"{sorted(missing_anchor_years)} -- those entries got a "
              f"fallback note without a named anchor file.")

    print(f"\nPrepared linkage text for {len(linkage_by_id)} of {len(nhanes)} "
          f"NHANES entries.")

    print("\n--- Sample results ---")
    for sample_id in ['nhanes-demographics-demo_d-2005',
                       'nhanes-dietary-drxfcd_d-2005']:
        if sample_id in linkage_by_id:
            print(f"  {sample_id}: {linkage_by_id[sample_id]}")
    for sid, text in list(linkage_by_id.items())[:1]:
        print(f"  {sid}: {text}")

    # Targeted text splicing (same approach used for the MIMIC-IV entries) --
    # this leaves every other byte of data.js untouched, avoiding a full
    # reformat / spurious diff of all 2600+ entries.
    backup_name = f"data.js.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy('data.js', backup_name)
    print(f"\nBacked up existing data.js to {backup_name}")

    patched = 0
    skipped_already_has_linkage = 0
    docurl_pattern = re.compile(r'"docUrl":\s*"[^"]*"')

    for ds_id, link_text in linkage_by_id.items():
        id_pos = content.find(f'"id": "{ds_id}"')
        if id_pos == -1:
            print(f"  WARNING: could not locate {ds_id} in data.js text")
            continue

        next_id_pos = content.find('"id":', id_pos + 1)
        window_end = next_id_pos if next_id_pos != -1 else len(content)

        if '"linkage":' in content[id_pos:window_end]:
            skipped_already_has_linkage += 1
            continue

        docurl_match = docurl_pattern.search(content, id_pos, window_end)
        if not docurl_match:
            print(f"  WARNING: no docUrl found for {ds_id}")
            continue

        escaped_link = link_text.replace('\\', '\\\\').replace('"', '\\"')
        insertion = ',\n    "linkage": "' + escaped_link + '"'
        insert_at = docurl_match.end()
        content = content[:insert_at] + insertion + content[insert_at:]
        patched += 1

    print(f"\nPatched {patched} entries. Skipped {skipped_already_has_linkage} "
          f"(already had a linkage field).")

    with open('data.js', 'w', encoding='utf-8') as f:
        f.write(content)

    print("Wrote data.js.")


if __name__ == '__main__':
    main()
