"""
debug_regenerate_desc.py

Diagnostic: calls the LLM for ONE truncated entry and prints the RAW
reply (before safe_json tries to parse it), so we can see exactly why
every retry in fix_truncated_phidu_desc.py's dry run came back
identical to the input -- something is causing safe_json to silently
fall back to the default instead of parsing a real new answer.

Usage: python3 debug_regenerate_desc.py
"""

import json
from extractor_phidu import nim_chat

schema = json.load(open("schema.json"))
ds_id = "phidu-pha-aust-aboriginal-males"
entry = schema[ds_id]

sheet = entry.get("sheet", entry.get("name", ""))
geo = entry.get("geo", "")
region = entry.get("region", "")
old_desc = entry.get("desc", "")

prompt = f"""Write ONE complete, well-formed sentence describing this Australian health dataset. Do not truncate or cut off mid-sentence -- keep it under 200 characters so it fits comfortably.

Dataset: {sheet.replace('_', ' ')}
Geography: {geo} ({region})
Previous (truncated) attempt, for context only -- do not just repeat it: "{old_desc}"

Return ONLY a JSON object: {{"desc": "<the complete one-sentence description>"}}"""

print("=== PROMPT ===")
print(prompt)
print("\n=== RAW REPLY ===")
reply = nim_chat([
    {"role": "system", "content": "You are a health data expert. Return ONLY valid JSON, no markdown. Always write a COMPLETE sentence ending in a period."},
    {"role": "user", "content": prompt},
], max_tokens=150)
print(repr(reply))
