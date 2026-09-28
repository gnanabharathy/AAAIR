"""
regenerate_datajs.py

Regenerates data.js from schema.json, preserving the SUBTYPE_TAG block
that lives below the DATASETS array in the existing data.js file.

This is the same logic that was previously run as a python3 -c one-liner
(documented in project_context.pdf) -- pulled into a standalone script so
it's not fragile to shell quoting.
"""

import json

with open("schema.json", "r", encoding="utf-8") as f:
    schema = json.load(f)

datasets = [
    {
        "id": k,
        "name": v.get("name", k),
        "desc": v.get("desc", ""),
        "source": v.get("source", ""),
        "subtypes": v.get("subtypes", []),
        "tasks": v.get("tasks", []),
        "last_updated": v.get("last_updated", ""),
        "docUrl": v.get("url", ""),
    }
    for k, v in schema.items()
]

with open("data.js", "r", encoding="utf-8") as f:
    existing = f.read()

idx = existing.find("const SUBTYPE_TAG")
tags = existing[idx:] if idx != -1 else ""

with open("data.js", "w", encoding="utf-8") as f:
    f.write("const DATASETS = ")
    json.dump(datasets, f, indent=2, ensure_ascii=False)
    f.write(";\n\n" + tags)

print(f"{len(datasets)} datasets")
