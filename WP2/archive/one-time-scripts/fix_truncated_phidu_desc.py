"""
fix_truncated_phidu_desc.py

Finds every PHIDU entry whose description was cut off mid-sentence
(doesn't end in . ! or ?) and regenerates just that description via
the LLM, using a stricter, higher-token-budget prompt aimed at
avoiding the same truncation.

This affects 26 of 950 PHIDU entries across multiple subtypes (not
just indigenous-health) -- likely caused by llm_generate_metadata's
underlying nim_chat call occasionally producing a 'reasoning' style
response that ate into the token budget before reaching the real
answer (see safe_json's reasoning_content handling), truncating the
description well before a natural sentence end.

Usage:
    python3 fix_truncated_phidu_desc.py                 # apply changes
    python3 fix_truncated_phidu_desc.py --dry-run        # preview only
"""

import argparse
import json
import re
import shutil
import time
from datetime import datetime

from extractor_phidu import nim_chat, safe_json

SCHEMA_FILE = "schema.json"


def is_truncated(desc):
    desc = desc.strip()
    if not desc:
        return True
    return not re.search(r'[.!?]\s*$', desc)


def regenerate_desc(ds_id, entry):
    sheet = entry.get("sheet", entry.get("name", ""))
    geo = entry.get("geo", "")
    region = entry.get("region", "")
    old_desc = entry.get("desc", "")

    prompt = f"""Write ONE complete, well-formed sentence describing this Australian health dataset. Do not truncate or cut off mid-sentence.

Dataset: {sheet.replace('_', ' ')}
Geography: {geo} ({region})
Previous (truncated) attempt, for context only -- do not just repeat it: "{old_desc}"

Return ONLY a JSON object: {{"desc": "<the complete one-sentence description>"}}"""

    reply = nim_chat([
        {"role": "system", "content": "You are a health data expert. Return ONLY valid JSON, no markdown. Always write a COMPLETE sentence ending in a period."},
        {"role": "user", "content": prompt},
    ], max_tokens=300)

    # Use a sentinel (not old_desc) as the fallback so we can tell
    # definitively whether safe_json actually parsed a real answer, vs
    # silently falling back -- the earlier version used old_desc as
    # the fallback, which made a PARSE FAILURE look identical to "the
    # LLM's new answer happens to equal the old one", hiding the real
    # problem (every one of the 26 dry-run "still truncated" results
    # was actually this silent fallback, not a genuine re-truncation).
    _PARSE_FAILED = object()
    result = safe_json(reply, default={"desc": _PARSE_FAILED})
    desc = result.get("desc", _PARSE_FAILED)

    if desc is _PARSE_FAILED:
        raise RuntimeError(f"Could not parse a JSON desc from the reply. "
                            f"Raw reply was: {reply!r}")

    return desc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    schema = json.load(open(SCHEMA_FILE))
    phidu_ids = [k for k, v in schema.items() if v.get("source") == "PHIDU"]

    truncated_ids = [k for k in phidu_ids if is_truncated(schema[k].get("desc", ""))]
    print(f"Found {len(truncated_ids)} truncated descriptions "
          f"({'DRY RUN' if args.dry_run else 'LIVE'})...\n")

    if not args.dry_run:
        backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(SCHEMA_FILE, backup_name)
        print(f"Backed up existing schema.json to {backup_name}\n")

    fixed = 0
    still_bad = []

    for i, ds_id in enumerate(truncated_ids, 1):
        entry = schema[ds_id]
        old_desc = entry.get("desc", "")

        new_desc = None
        last_error = None
        for attempt in range(3):
            try:
                candidate = regenerate_desc(ds_id, entry)
                time.sleep(1)
            except Exception as e:
                last_error = e
                continue
            if not is_truncated(candidate):
                new_desc = candidate
                break
            last_error = f"regenerated text was still truncated: {candidate!r}"

        if new_desc is None:
            print(f"  [{i}/{len(truncated_ids)}] FAILED after 3 attempts: {ds_id}")
            print(f"    last error: {last_error}")
            still_bad.append(ds_id)
            continue

        print(f"  [{i}/{len(truncated_ids)}] FIXED: {ds_id}")
        print(f"    old: {old_desc}")
        print(f"    new: {new_desc}")
        fixed += 1

        if not args.dry_run:
            entry["desc"] = new_desc
            with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"DONE: {fixed} fixed, {len(still_bad)} still need attention, "
          f"of {len(truncated_ids)} total")
    if still_bad:
        print(f"Still needing attention: {still_bad}")


if __name__ == "__main__":
    main()
