#!/usr/bin/env python3
"""
scan_phidu.py — Scan PHIDU xlsx files and generate datasets_phidu.csv
Each sheet in each xlsx file becomes one dataset entry.

Usage: python3 scan_phidu.py
Output: datasets_phidu.csv
"""

import csv
import re
import os
import urllib.request
import pandas as pd
from collections import Counter

OUTPUT_FILE = "datasets_phidu.csv"
TMP_DIR = "/tmp/phidu"
os.makedirs(TMP_DIR, exist_ok=True)

# All PHIDU xlsx files from https://phidu.torrens.edu.au/social-health-atlases/data
PHIDU_FILES = [
    # === Whole Population: PHA by location ===
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_aust.xlsx",     "source": "phidu-pha-aust",    "geo": "Population Health Area", "subtype": "health-status",       "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_nsw.xlsx",      "source": "phidu-pha-nsw",     "geo": "Population Health Area", "subtype": "health-status",       "region": "NSW"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_vic.xlsx",      "source": "phidu-pha-vic",     "geo": "Population Health Area", "subtype": "health-status",       "region": "Vic"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_qld.xlsx",      "source": "phidu-pha-qld",     "geo": "Population Health Area", "subtype": "health-status",       "region": "Qld"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_sa.xlsx",       "source": "phidu-pha-sa",      "geo": "Population Health Area", "subtype": "health-status",       "region": "SA"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_wa.xlsx",       "source": "phidu-pha-wa",      "geo": "Population Health Area", "subtype": "health-status",       "region": "WA"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_tas.xlsx",      "source": "phidu-pha-tas",     "geo": "Population Health Area", "subtype": "health-status",       "region": "Tas"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_nt.xlsx",       "source": "phidu-pha-nt",      "geo": "Population Health Area", "subtype": "health-status",       "region": "NT"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_act.xlsx",      "source": "phidu-pha-act",     "geo": "Population Health Area", "subtype": "health-status",       "region": "ACT"},

    # === Whole Population: PHA by topic ===
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_demographic_social_aust.xlsx",   "source": "phidu-pha-demographics",    "geo": "Population Health Area", "subtype": "social-determinants", "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_health_status_aust.xlsx",        "source": "phidu-pha-health-status",   "geo": "Population Health Area", "subtype": "health-status",       "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/pha/phidu_data_pha_use_provision_health_aust.xlsx", "source": "phidu-pha-health-services", "geo": "Population Health Area", "subtype": "health-services",     "region": "Australia"},

    # === Whole Population: LGA ===
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/lga/phidu_data_lga_aust.xlsx",        "source": "phidu-lga-aust",    "geo": "Local Government Area", "subtype": "health-status", "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/lga/phidu_data_lga_nsw_act.xlsx",     "source": "phidu-lga-nsw-act", "geo": "Local Government Area", "subtype": "health-status", "region": "NSW/ACT"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/lga/phidu_data_lga_vic.xlsx",         "source": "phidu-lga-vic",     "geo": "Local Government Area", "subtype": "health-status", "region": "Vic"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/lga/phidu_data_lga_qld.xlsx",         "source": "phidu-lga-qld",     "geo": "Local Government Area", "subtype": "health-status", "region": "Qld"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/lga/phidu_data_lga_sa.xlsx",          "source": "phidu-lga-sa",      "geo": "Local Government Area", "subtype": "health-status", "region": "SA"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/lga/phidu_data_lga_wa.xlsx",          "source": "phidu-lga-wa",      "geo": "Local Government Area", "subtype": "health-status", "region": "WA"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/lga/phidu_data_lga_tas.xlsx",         "source": "phidu-lga-tas",     "geo": "Local Government Area", "subtype": "health-status", "region": "Tas"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/lga/phidu_data_lga_nt.xlsx",          "source": "phidu-lga-nt",      "geo": "Local Government Area", "subtype": "health-status", "region": "NT"},

    # === Whole Population: PHN ===
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/phn_pha_parts/phidu_data_phn_pha_parts_aust.xlsx", "source": "phidu-phn-pha", "geo": "Primary Health Network", "subtype": "health-services", "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/phn_lga_parts/phidu_data_phn_lga_aust.xlsx",       "source": "phidu-phn-lga", "geo": "Primary Health Network", "subtype": "health-services", "region": "Australia"},

    # === Whole Population: Socioeconomic Disadvantage ===
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/quintiles/phidu_data_quintiles_aust.xlsx",                      "source": "phidu-quintiles",            "geo": "Socioeconomic Disadvantage", "subtype": "social-determinants", "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/quintiles-phn/phidu_data_phn_quintiles_aust.xlsx",               "source": "phidu-quintiles-phn",        "geo": "Socioeconomic Disadvantage", "subtype": "social-determinants", "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/quintiles-time-series/phidu_data_time_series_quintiles_aust.xlsx","source": "phidu-quintiles-timeseries", "geo": "Socioeconomic Disadvantage", "subtype": "social-determinants", "region": "Australia"},

    # === Whole Population: Remoteness ===
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/remoteness/phidu_data_remoteness_aust.xlsx",                       "source": "phidu-remoteness",            "geo": "Remoteness Area", "subtype": "social-determinants", "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-aust/remoteness-time-series/phidu_data_time_series_remoteness_aust.xlsx","source": "phidu-remoteness-timeseries", "geo": "Remoteness Area", "subtype": "social-determinants", "region": "Australia"},

    # === Aboriginal & Torres Strait Islander ===
    {"url": "https://phidu.torrens.edu.au/current/data/atsi-sha/phidu_atsi_data_ia_aust.xlsx",                        "source": "phidu-atsi-ia",                   "geo": "Indigenous Area",            "subtype": "indigenous-health",   "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/atsi-sha/phidu_atsi_data_phn_aust.xlsx",                       "source": "phidu-atsi-phn",                  "geo": "Primary Health Network",     "subtype": "indigenous-health",   "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/atsi-sha/phidu_atsi_data_quintiles_aust.xlsx",                 "source": "phidu-atsi-quintiles",            "geo": "Socioeconomic Disadvantage", "subtype": "indigenous-health",   "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/atsi-sha/phidu_atsi_data_quintiles_time_series_aust.xlsx",     "source": "phidu-atsi-quintiles-timeseries", "geo": "Socioeconomic Disadvantage", "subtype": "indigenous-health",   "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/atsi-sha/phidu_atsi_data_remoteness_aust.xlsx",                "source": "phidu-atsi-remoteness",           "geo": "Remoteness Area",            "subtype": "indigenous-health",   "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/atsi-sha/phidu_atsi_data_remoteness_time_series_aust.xlsx",    "source": "phidu-atsi-remoteness-timeseries","geo": "Remoteness Area",            "subtype": "indigenous-health",   "region": "Australia"},

    # === Indigenous Status Comparison ===
    {"url": "https://phidu.torrens.edu.au/current/data/sha-topics/Indigenous-status-comparison/phidu_Indigenous_status_comparison_data_ia_aust.xlsx",        "source": "phidu-indigenous-comparison-ia",         "geo": "Indigenous Area",            "subtype": "indigenous-health", "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-topics/Indigenous-status-comparison/phidu_Indigenous_status_comparison_data_quintiles_aust.xlsx",  "source": "phidu-indigenous-comparison-quintiles",  "geo": "Socioeconomic Disadvantage", "subtype": "indigenous-health", "region": "Australia"},
    {"url": "https://phidu.torrens.edu.au/current/data/sha-topics/Indigenous-status-comparison/phidu_Indigenous_status_comparison_data_remoteness_aust.xlsx", "source": "phidu-indigenous-comparison-remoteness", "geo": "Remoteness Area",            "subtype": "indigenous-health", "region": "Australia"},
]

# Sheets to skip (non-data)
SKIP_SHEETS = {
    "Front_page", "Topics", "Contents", "Key", "Notes",
    "front_page", "topics", "contents", "key", "notes",
    "Front page", "Contents page",
}

def download_file(url, filename):
    path = os.path.join(TMP_DIR, filename)
    if os.path.exists(path):
        print(f"  Already downloaded: {filename}")
        return path
    print(f"  Downloading {filename}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(path, "wb") as f:
            f.write(r.read())
    print(f"  Saved: {filename}")
    return path

def sheet_to_id(source, sheet_name):
    name = sheet_name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return f"{source}-{name}"

def sheet_to_label(sheet_name, region, geo):
    label = sheet_name.replace("_", " ").title()
    return f"{label} — {geo} ({region})"

def main():
    rows = []
    seen_ids = set()

    for file_info in PHIDU_FILES:
        url = file_info["url"]
        filename = url.split("/")[-1]
        source = file_info["source"]
        region = file_info["region"]
        geo = file_info["geo"]

        print(f"\nProcessing {filename} [{region}]...")
        try:
            path = download_file(url, filename)
            xl = pd.ExcelFile(path)
            data_sheets = [
                s for s in xl.sheet_names
                if s not in SKIP_SHEETS and not s.startswith("_")
            ]
            print(f"  {len(data_sheets)} data sheets")

            for sheet in data_sheets:
                ds_id = sheet_to_id(source, sheet)

                # Ensure unique ID
                original_id = ds_id
                counter = 2
                while ds_id in seen_ids:
                    ds_id = f"{original_id}-{counter}"
                    counter += 1
                seen_ids.add(ds_id)

                label = sheet_to_label(sheet, region, geo)
                rows.append({
                    "id": ds_id,
                    "url": url,
                    "sheet": sheet,
                    "subtype": file_info["subtype"],
                    "geo": geo,
                    "region": region,
                    "source_file": filename,
                    "label": label,
                })

        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    # Write CSV
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "url", "sheet", "subtype", "geo", "region", "source_file", "label"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} datasets to {OUTPUT_FILE}")

    subtypes = Counter(r["subtype"] for r in rows)
    print("\nBy subtype:")
    for subtype, count in sorted(subtypes.items()):
        print(f"  {subtype}: {count}")

    geos = Counter(r["geo"] for r in rows)
    print("\nBy geography:")
    for geo, count in sorted(geos.items()):
        print(f"  {geo}: {count}")

if __name__ == "__main__":
    main()
