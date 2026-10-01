"""
audit_phidu_quality.py

Full-population automated audit of all PHIDU entries in schema.json,
checking three dimensions: name quality, description quality, and
subtype classification. Surfaces candidates for manual review --
it does NOT auto-fix anything, since judging whether a name/desc is
actually WRONG (vs just terse) needs a human look at the real content.

Checks:

NAME:
  - name equals the raw sheet name (Title Case), meaning LLM naming
    likely never ran / failed and the fallback default was used
  - name > 80 chars (violates the extractor's own stated limit)
  - name contains a literal newline or leftover underscore (cleanup
    that should have happened but didn't)

DESCRIPTION:
  - desc mentions a DIFFERENT state/territory than this entry's own
    'region' field (e.g. an SA-scoped entry whose desc says "New South
    Wales") -- a real content-accuracy bug, not just terse wording
  - desc is suspiciously short (<20 chars) or empty
  - desc looks like an unclean LLM reasoning trace (starts with
    "We need", "Let me", "Maybe", or contains "```")
  - desc is IDENTICAL to another entry's desc (possible copy-paste /
    caching bug reusing one sheet's metadata for a different sheet)

SUBTYPE:
  - flags entries whose subtype seems like a mismatch based on simple
    keyword signals in the sheet/name/desc (e.g. contains "death" or
    "hospital" but tagged social-determinants instead of health-status;
    contains "income" or "employ" but tagged health-status instead of
    social-determinants). This is a heuristic, not a ground truth --
    every hit here needs a human judgment call, this just narrows down
    which ~974 entries are worth a human look instead of all of them.

Usage: python3 audit_phidu_quality.py
Writes phidu_audit_report.json with the full findings, and prints a
summary count per issue type.
"""

import json
import re
from collections import Counter, defaultdict

STATE_NAMES = {
    "NSW": ["New South Wales"],
    "Vic": ["Victoria"],
    "Qld": ["Queensland"],
    "SA": ["South Australia"],
    "WA": ["Western Australia"],
    "Tas": ["Tasmania"],
    "NT": ["Northern Territory"],
    "ACT": ["Australian Capital Territory"],
}

HEALTH_STATUS_KEYWORDS = ["death", "mortality", "hospital", "disease", "disability",
                           "cancer", "diabetes", "smoking", "obesity", "immunisation",
                           "birth", "life expectancy", "carer"]
SOCIAL_DETERMINANTS_KEYWORDS = ["income", "employ", "unemploy", "education",
                                 "housing", "socioeconomic", "seifa",
                                 "disadvantage", "migrant"]
HEALTH_SERVICES_KEYWORDS = ["medicare", "mbs", "pbs", "gp ", "general practitioner",
                             "service", "provider", "workforce"]

schema = json.load(open("schema.json"))
phidu = {k: v for k, v in schema.items() if v.get("source") == "PHIDU"}
print(f"Auditing {len(phidu)} PHIDU entries...\n")

issues = defaultdict(list)

# --- Precompute desc -> [ids] for duplicate-desc check ---
desc_to_ids = defaultdict(list)
for k, v in phidu.items():
    desc_to_ids[v.get("desc", "")].append(k)

for k, v in phidu.items():
    name = v.get("name", "")
    desc = v.get("desc", "")
    sheet = v.get("sheet", "")
    region = v.get("region", "")
    subtypes = v.get("subtypes", [])

    # NAME checks
    if sheet and name == sheet.replace("_", " ").title():
        issues["name_is_raw_sheet_name"].append(k)
    if len(name) > 80:
        issues["name_too_long"].append(k)
    if "\n" in name or "_" in name:
        issues["name_has_leftover_artifacts"].append(k)

    # DESCRIPTION checks
    if region in STATE_NAMES:
        for other_region, names in STATE_NAMES.items():
            if other_region == region:
                continue
            if any(n in desc for n in names):
                issues["desc_wrong_region_mentioned"].append(
                    (k, region, other_region))
                break
    if len(desc.strip()) < 20:
        issues["desc_too_short"].append(k)
    if re.match(r"^(We need|Let me|Maybe|I need|```)", desc.strip()):
        issues["desc_looks_like_llm_reasoning_leak"].append(k)
    if len(desc_to_ids[desc]) > 1 and desc.strip():
        issues["desc_duplicated_across_entries"].append(k)

    # SUBTYPE heuristic checks
    combined_text = f"{name} {desc} {sheet}".lower()
    has_health_status_kw = any(kw in combined_text for kw in HEALTH_STATUS_KEYWORDS)
    has_social_kw = any(kw in combined_text for kw in SOCIAL_DETERMINANTS_KEYWORDS)
    has_services_kw = any(kw in combined_text for kw in HEALTH_SERVICES_KEYWORDS)

    if has_health_status_kw and "health-status" not in subtypes:
        issues["subtype_missing_health_status_signal"].append(k)
    if has_services_kw and "health-services" not in subtypes:
        issues["subtype_missing_health_services_signal"].append(k)
    # Only flag social-determinants mismatch if it looks clearly
    # socioeconomic AND is currently tagged as health-status (the two
    # most commonly confused categories in this dataset)
    if has_social_kw and not has_health_status_kw and "social-determinants" not in subtypes \
            and "health-status" in subtypes:
        issues["subtype_possible_social_vs_health_status_confusion"].append(k)

# --- Print summary ---
print("=" * 60)
print("SUMMARY (counts, not necessarily all distinct entries)")
print("=" * 60)
for issue_type, hits in issues.items():
    print(f"  {issue_type}: {len(hits)}")

total_flagged = len(set(
    h[0] if isinstance(h, tuple) else h
    for hits in issues.values() for h in hits
))
print(f"\nTotal DISTINCT entries flagged by at least one check: {total_flagged} "
      f"of {len(phidu)} ({100*total_flagged/len(phidu):.1f}%)")

# --- Write full report ---
report = {}
for issue_type, hits in issues.items():
    report[issue_type] = [
        {"id": h[0], "detail": h[1:]} if isinstance(h, tuple) else {"id": h}
        for h in hits
    ]
with open("phidu_audit_report.json", "w") as f:
    json.dump(report, f, indent=2)
print("\nFull details written to phidu_audit_report.json")
