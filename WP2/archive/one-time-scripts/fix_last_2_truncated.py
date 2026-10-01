"""
fix_last_2_truncated.py

Handles the 2 entries that fix_truncated_phidu_desc.py couldn't fix
even after 3 retries at max_tokens=300 -- their raw replies showed the
JSON itself being cut off before the closing quote/brace, meaning 300
tokens genuinely isn't enough room for these two's naturally longer
descriptions. Retries just these 2 with a larger max_tokens=500.

Usage:
    python3 fix_last_2_truncated.py                 # apply changes
    python3 fix_last_2_truncated.py --dry-run        # preview only
"""

import argparse
import json
import re
import shutil
import time
from datetime import datetime

from extractor_phidu import nim_chat, safe_json

SCHEMA_FILE = "schema.json"
TARGET_IDS = ["phidu-pha-aust-migrants-total", "phidu-pha-aust-admiss-principal-diag-females"]


def is_truncated(desc):
    desc = desc.strip()
    if not desc:
        return True
    return not re.search(r'[.!?]\s*$', desc)


def regenerate_desc(entry):
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
    ], max_tokens=500)

    _PARSE_FAILED = object()
    result = safe_json(reply, default={"desc": _PARSE_FAILED})
    desc = result.get("desc", _PARSE_FAILED)
    if desc is _PARSE_FAILED:
        raise RuntimeError(f"Could not parse. Raw reply: {reply!r}")
    return desc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    schema = json.load(open(SCHEMA_FILE))

    if not args.dry_run:
        backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(SCHEMA_FILE, backup_name)
        print(f"Backed up existing schema.json to {backup_name}\n")

    for ds_id in TARGET_IDS:
        entry = schema[ds_id]
        old_desc = entry.get("desc", "")

        new_desc = None
        last_error = None
        for attempt in range(3):
            try:
                candidate = regenerate_desc(entry)
                time.sleep(1)
            except Exception as e:
                last_error = e
                continue
            if not is_truncated(candidate):
                new_desc = candidate
                break
            last_error = f"still truncated: {candidate!r}"

        if new_desc is None:
            print(f"FAILED after 3 attempts: {ds_id}")
            print(f"  last error: {last_error}")
            continue

        print(f"FIXED: {ds_id}")
        print(f"  old: {old_desc}")
        print(f"  new: {new_desc}")

        if not args.dry_run:
            entry["desc"] = new_desc
            with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
