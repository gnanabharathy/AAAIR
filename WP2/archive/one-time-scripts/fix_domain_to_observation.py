"""
fix_domain_to_observation.py

One-off correction: the harmonize_concept_specs.py run for the drxfcd
family set domain_id to "Food", based on the LLM's claim that OMOP CDM
5.3 has a dedicated Food domain. That claim was checked against the
official OHDSI CommonDataModel documentation (cdm53.html) and found to
be false -- no such domain exists there. This script corrects
domain_id to "Observation" (a real, documented standard domain)
across the affected spec files, leaving everything else untouched.

Usage: python3 fix_domain_to_observation.py <ds_id1> <ds_id2> ...
"""

import json
import sys

ds_ids = sys.argv[1:]
if not ds_ids:
    print("Usage: python3 fix_domain_to_observation.py <ds_id1> <ds_id2> ...")
    sys.exit(1)

for ds_id in ds_ids:
    spec_path = f"dqd/concept_specs/spec_{ds_id}.json"
    try:
        spec = json.load(open(spec_path))
    except FileNotFoundError:
        print(f"SKIP: {spec_path} not found")
        continue

    old_domain = spec.get("domain_id")
    spec["domain_id"] = "Observation"
    spec["domain_id_correction_note"] = (
        f"Changed from '{old_domain}' to 'Observation' -- 'Food' is not "
        f"a real OMOP CDM 5.3 domain (verified against official OHDSI "
        f"CommonDataModel docs); the LLM's earlier claim that it was a "
        f"built-in domain was incorrect."
    )

    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"Updated {spec_path}: domain_id '{old_domain}' -> 'Observation'")
