"""
reclassify_phidu_subtypes.py

Re-classifies the subtype of EVERY PHIDU entry in schema.json by
calling the LLM per-entry, based on that entry's own name/desc/sheet
content -- replacing the old behaviour where every sheet in a workbook
silently inherited one hardcoded subtype from the whole file's config
in TEST_FILES, regardless of what that individual sheet was actually
about.

Runs on ALL 974 PHIDU entries, not just the ~135 the audit script
flagged -- the audit's keyword heuristics were necessarily narrow and
almost certainly missed some mis-tagged entries that don't happen to
contain one of its specific keywords.

Saves progress after every entry (resumable if interrupted), and skips
any entry whose current subtype the LLM confirms is already correct
(no unnecessary rewrite). Uses the same NIM_API_KEY / rate-limiting
pattern as extractor_phidu.py.

Usage:
    python3 reclassify_phidu_subtypes.py                 # apply changes
    python3 reclassify_phidu_subtypes.py --dry-run        # preview only, no writes
"""

import argparse
import json
import shutil
import time
from datetime import datetime

from extractor_phidu import llm_classify_subtype, VALID_PHIDU_SUBTYPES, SCHEMA_FILE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                         help="Preview reclassifications without writing schema.json")
    args = parser.parse_args()

    schema = json.load(open(SCHEMA_FILE))
    phidu_ids = [k for k, v in schema.items() if v.get("source") == "PHIDU"]
    print(f"Reclassifying {len(phidu_ids)} PHIDU entries "
          f"({'DRY RUN -- no changes will be saved' if args.dry_run else 'LIVE'})...\n")

    if not args.dry_run:
        backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(SCHEMA_FILE, backup_name)
        print(f"Backed up existing schema.json to {backup_name}\n")

    changed = 0
    unchanged = 0
    failed = 0

    for i, ds_id in enumerate(phidu_ids, 1):
        entry = schema[ds_id]
        old_subtypes = entry.get("subtypes", [])
        old_subtype = old_subtypes[0] if old_subtypes else None

        try:
            new_subtype = llm_classify_subtype(
                entry.get("sheet", entry.get("name", "")),
                entry.get("desc", ""),
                entry.get("geo", ""),
                entry.get("region", ""),
            )
            time.sleep(1)
        except Exception as e:
            print(f"  [{i}/{len(phidu_ids)}] FAILED: {ds_id} -- {e}")
            failed += 1
            continue

        if new_subtype == old_subtype:
            unchanged += 1
            print(f"  [{i}/{len(phidu_ids)}] OK (unchanged): {ds_id} -> {new_subtype}")
        else:
            changed += 1
            print(f"  [{i}/{len(phidu_ids)}] CHANGED: {ds_id} :: "
                  f"{old_subtype} -> {new_subtype}")
            if not args.dry_run:
                entry["subtypes"] = [new_subtype]
                with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
                    json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"DONE: {changed} changed, {unchanged} unchanged, {failed} failed "
          f"of {len(phidu_ids)} total")
    if args.dry_run:
        print("(dry run -- schema.json was not modified)")


if __name__ == "__main__":
    main()
