"""
fix_dsbi_family_domain.py

One-off correction: the harmonize_concept_specs.py run for the
dsbi/dsii/dspi family set domain_id to "Ingredient". Verified against
official OHDSI documentation (DrugExposureDiagnostics tutorial +
Custom Concepts docs) that "Ingredient" is a concept_class_id value
within the Drug domain (e.g. RxNorm's "Ingredient" class for
acetaminophen has domain_id=Drug, concept_class_id=Ingredient) -- it
is not a domain itself. Corrects domain_id to "Drug" and
concept_class_id to "Ingredient" across the affected spec files.

Usage: python3 fix_dsbi_family_domain.py
"""

import json

ds_ids = ["nhanes-dietary-dsbi-1999", "nhanes-dietary-dsii-1999", "nhanes-dietary-dspi-1999"]

for ds_id in ds_ids:
    spec_path = f"dqd/concept_specs/spec_{ds_id}.json"
    spec = json.load(open(spec_path))

    old_domain = spec.get("domain_id")
    old_class = spec.get("concept_class_id")

    spec["domain_id"] = "Drug"
    spec["concept_class_id"] = "Ingredient"
    spec["domain_id_correction_note"] = (
        f"Changed domain_id from '{old_domain}' to 'Drug', and "
        f"concept_class_id from '{old_class}' to 'Ingredient' -- "
        f"verified against official OHDSI docs that 'Ingredient' is a "
        f"concept_class_id value within the Drug domain (e.g. RxNorm's "
        f"'Ingredient' class), not a domain itself."
    )

    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"Fixed {spec_path}: domain_id '{old_domain}'->'Drug', "
          f"concept_class_id '{old_class}'->'Ingredient'")
