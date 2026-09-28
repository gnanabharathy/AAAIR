"""
fix_varlk_specs.py

One-off manual correction: the LLM's generated specs for varlk_c-2003
and varlk_d-2005 had concept_name_column and concept_code_column
reversed, and invented a concept_code_column ("FFQ_VAR_VALUE") that
doesn't exist in the actual file. Verified against real sample data
(inspect_xpt_sample.py) that FFQ_VAR is the numeric code and VALUE is
the human-readable food description -- the opposite of what was
generated.

Usage: python3 fix_varlk_specs.py
"""

import json

for ds_id in ["nhanes-dietary-varlk_c-2003", "nhanes-dietary-varlk_d-2005"]:
    spec_path = f"dqd/concept_specs/spec_{ds_id}.json"
    spec = json.load(open(spec_path))

    old_name_col = spec.get("concept_name_column")
    old_code_col = spec.get("concept_code_column")

    spec["concept_name_column"] = "VALUE"
    spec["concept_code_column"] = "FFQ_VAR"
    spec["manual_correction_note"] = (
        f"LLM originally set concept_name_column='{old_name_col}', "
        f"concept_code_column='{old_code_col}' -- the latter referenced "
        f"a column ('FFQ_VAR_VALUE') that does not exist in the actual "
        f"file. Verified against real sample data: FFQ_VAR is the "
        f"numeric code, VALUE is the human-readable food description. "
        f"Corrected manually."
    )

    with open(spec_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"Fixed {spec_path}")
