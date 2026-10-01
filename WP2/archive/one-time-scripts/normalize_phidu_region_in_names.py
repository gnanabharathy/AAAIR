"""
normalize_phidu_region_in_names.py

Standardises how region appears in PHIDU dataset names, without
rewriting the names themselves:
  - region == 'Australia': name is left as-is (no suffix needed --
    national data doesn't need to say "Australia" in every title).
  - region == a specific state/territory, AND the name doesn't already
    mention that state (by full name or abbreviation): appends
    " (<abbreviation>)" to the end of the existing name.
  - region == a specific state, and the name ALREADY mentions it
    (however phrased): left untouched -- no double-tagging.

This only ever APPENDS a short, parenthetical suffix; it never removes
or rewrites the substantive wording a name already has, so there's no
risk of introducing a new factual error into an otherwise-correct name.

Usage:
    python3 normalize_phidu_region_in_names.py                 # apply
    python3 normalize_phidu_region_in_names.py --dry-run        # preview
"""

import argparse
import json
import re
import shutil
from datetime import datetime

SCHEMA_FILE = "schema.json"

STATE_WORDS = {
    "NSW": ["NSW", "New South Wales"],
    "Vic": ["Vic", "Victoria", "Victorian"],
    "Qld": ["Qld", "Queensland"],
    "SA": ["SA", "South Australia", "South Australian"],
    "WA": ["WA", "Western Australia", "Western Australian"],
    "Tas": ["Tas", "Tasmania", "Tasmanian"],
    "NT": ["NT", "Northern Territory"],
    "ACT": ["ACT", "Australian Capital Territory"],
}


def already_mentions_region(name, region):
    words = STATE_WORDS.get(region, [])
    name_lower = name.lower()
    for w in words:
        # Case-insensitive whole-word match -- catches "QLD", "Qld",
        # "qld", "VIC", etc. all as the same abbreviation, which the
        # original case-sensitive check missed (PHIDU titles use
        # ALL-CAPS abbreviations like "QLD"/"VIC" as often as
        # title-case ones like "Qld"/"Vic").
        if re.search(r'\b' + re.escape(w.lower()) + r'\b', name_lower):
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    d = json.load(open(SCHEMA_FILE))
    phidu = {k: v for k, v in d.items() if v.get("source") == "PHIDU"}

    to_update = []
    for k, v in phidu.items():
        region = v.get("region", "")
        name = v.get("name", "")
        if region not in STATE_WORDS:
            continue  # Australia-wide or unknown region -- leave as-is
        if already_mentions_region(name, region):
            continue  # already tagged, don't double up
        new_name = f"{name} ({region})"
        to_update.append((k, name, new_name))

    print(f"Found {len(to_update)} names needing a region suffix "
          f"({'DRY RUN' if args.dry_run else 'LIVE'})\n")
    for k, old_name, new_name in to_update[:30]:
        print(f"  {k}:")
        print(f"    old: {old_name}")
        print(f"    new: {new_name}")
    if len(to_update) > 30:
        print(f"  ... and {len(to_update) - 30} more")

    if not to_update:
        print("\nNothing to change.")
        return

    if not args.dry_run:
        backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(SCHEMA_FILE, backup_name)
        print(f"\nBacked up existing schema.json to {backup_name}")

        for k, old_name, new_name in to_update:
            d[k]["name"] = new_name

        with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)

        print(f"Wrote schema.json with {len(to_update)} names updated.")


if __name__ == "__main__":
    main()
