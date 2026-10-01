"""
fix_final_one.py

Final holdout: phidu-pha-aust-admiss-principal-diag-females keeps
triggering the model into leaking an internal reasoning/formatting
check ("Check for quotes inside: ...") instead of returning clean
JSON, likely because its content mentions a quoted phrase
("ischaemic heart disease...") that makes the model second-guess its
own JSON quoting. Sidesteps this by asking for PLAIN TEXT (no JSON,
no quote-escaping concerns at all) and wrapping it in JSON myself
afterwards.

Usage:
    python3 fix_final_one.py                 # apply
    python3 fix_final_one.py --dry-run        # preview
"""

import argparse
import json
import re
import shutil
import time
from datetime import datetime

from extractor_phidu import nim_chat

SCHEMA_FILE = "schema.json"
TARGET_ID = "phidu-pha-aust-admiss-principal-diag-females"


def is_truncated(desc):
    desc = desc.strip()
    return (not desc) or (not re.search(r'[.!?]\s*$', desc))


def regenerate_plain_text(entry):
    sheet = entry.get("sheet", entry.get("name", ""))
    geo = entry.get("geo", "")
    region = entry.get("region", "")

    prompt = f"""Write exactly one complete sentence describing this dataset. Output ONLY the sentence itself as plain text -- no JSON, no quotation marks around it, no markdown, no preamble, no explanation. Just the sentence, ending in a period.

Dataset: {sheet.replace('_', ' ')}
Geography: {geo} ({region})"""

    reply = nim_chat([
        {"role": "system", "content": "Output only the requested plain-text sentence. Nothing else."},
        {"role": "user", "content": prompt},
    ], max_tokens=200)

    # Clean up: strip whitespace, strip a leading/trailing quote if the
    # model added one anyway, strip any markdown fence.
    text = reply.strip()
    text = re.sub(r'^```[a-z]*\n?', '', text, flags=re.I)
    text = re.sub(r'\n?```$', '', text)
    text = text.strip().strip('"').strip()
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    schema = json.load(open(SCHEMA_FILE))
    entry = schema[TARGET_ID]
    old_desc = entry.get("desc", "")

    new_desc = None
    last_raw = None
    for attempt in range(3):
        try:
            candidate = regenerate_plain_text(entry)
            last_raw = candidate
            time.sleep(1)
        except Exception as e:
            last_raw = f"ERROR: {e}"
            continue
        if not is_truncated(candidate):
            new_desc = candidate
            break

    if new_desc is None:
        print(f"FAILED after 3 attempts. Last raw output: {last_raw!r}")
        return

    print(f"FIXED: {TARGET_ID}")
    print(f"  old: {old_desc}")
    print(f"  new: {new_desc}")

    if not args.dry_run:
        backup_name = f"schema.json.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(SCHEMA_FILE, backup_name)
        print(f"\nBacked up existing schema.json to {backup_name}")
        entry["desc"] = new_desc
        with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
        print("Wrote schema.json.")


if __name__ == "__main__":
    main()
