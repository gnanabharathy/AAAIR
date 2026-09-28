"""
merge_schema.py

Merges per-source schema files (schema_ptbxl.json, schema_tcga.json,
schema_gnomad.json, etc.) into the main schema.json. Run this from the
project root, where schema.json and the source-specific files all live.

Safe by design:
  - Reports which keys are NEW vs which keys already exist and would be
    OVERWRITTEN, before writing anything.
  - Makes a timestamped backup of schema.json before overwriting it.
  - Only merges files that actually exist in the current directory --
    skips missing ones without erroring, so you can run this after
    populating just one source (e.g. only schema_ptbxl.json present).
"""

import json
import shutil
from datetime import datetime

MAIN_SCHEMA = "schema.json"

# Add new source files here as you build more extractors.
SOURCE_FILES = [
    "schema_ptbxl.json",
    "schema_tcga.json",
    "schema_gnomad.json",
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    main_schema = load_json(MAIN_SCHEMA)
    print(f"Loaded {MAIN_SCHEMA}: {len(main_schema)} existing entries.")

    new_keys = []
    overwritten_keys = []

    for source_file in SOURCE_FILES:
        try:
            source_schema = load_json(source_file)
        except FileNotFoundError:
            print(f"  Skipping {source_file} (not found in current directory).")
            continue

        for key, entry in source_schema.items():
            if key in main_schema:
                overwritten_keys.append((source_file, key))
            else:
                new_keys.append((source_file, key))
            main_schema[key] = entry

        print(f"  Merged {source_file}: {len(source_schema)} entries.")

    print(f"\n{len(new_keys)} NEW entries will be added.")
    if overwritten_keys:
        print(f"{len(overwritten_keys)} EXISTING entries will be OVERWRITTEN:")
        for source_file, key in overwritten_keys:
            print(f"  {key}  (from {source_file})")
    else:
        print("No existing entries will be overwritten.")

    if not new_keys and not overwritten_keys:
        print("\nNothing to merge -- no source files found. Exiting without changes.")
        return

    backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy(MAIN_SCHEMA, backup_name)
    print(f"\nBacked up existing {MAIN_SCHEMA} to {backup_name}.")

    with open(MAIN_SCHEMA, "w", encoding="utf-8") as f:
        json.dump(main_schema, f, indent=2, ensure_ascii=False)

    print(f"Wrote {MAIN_SCHEMA}. Total entries now: {len(main_schema)}.")
    print("\nNext step: run your existing 'Regenerate data.js' script so the "
          "UI picks up the new entries.")


if __name__ == "__main__":
    main()
