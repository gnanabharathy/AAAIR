import os, sys, json, re, csv, urllib.request, urllib.error, webbrowser

# ---------------------------------------------------------------------------
# Load .env from the same directory as this script
# ---------------------------------------------------------------------------
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    for line in open(_env_path).read().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

NIM_API_KEY      = os.getenv("NIM_API_KEY", "")
NIM_MODEL        = os.getenv("NIM_MODEL",   "meta/llama-3.3-70b-instruct")
NIM_BASE_URL     = os.getenv("NIM_BASE_URL","https://integrate.api.nvidia.com/v1")
NIM_ENRICH_BATCH = 15


# ---------------------------------------------------------------------------
# System prompts — one per NIM task
# ---------------------------------------------------------------------------

SYSTEM_ENRICH = """You are a biomedical data dictionary specialist.
Your job is to analyse NHANES and other open health dataset variables and classify them.
You always return a valid JSON array — same length and order as the input.
Never add markdown fences, never add explanation, never skip variables."""

SYSTEM_LAST_UPDATED = """You are a document metadata extractor.
Your job is to find dates in dataset documentation pages.
You always return valid JSON with a single key. No markdown, no explanation."""

SYSTEM_CARD_INFO = """You are a biomedical dataset cataloguer.
Your job is to read dataset documentation and extract structured catalogue information.
You always return valid JSON with exactly the keys requested. No markdown, no explanation."""

# ---------------------------------------------------------------------------
# Step 1 — Fetch HTML
# ---------------------------------------------------------------------------

def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", errors="ignore")

def fetch_last_modified(url):
    """Get Last-Modified date from HTTP response header."""
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            last_modified = r.headers.get("Last-Modified")
        if last_modified:
            # Convert "Thu, 31 Jul 2025 15:15:07 GMT" to "July 2025"
            from email.utils import parsedate
            from datetime import datetime
            parsed = parsedate(last_modified)
            if parsed:
                dt = datetime(*parsed[:6])
                return dt.strftime("%B %Y")
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# Step 2 — Regex: extract all variables from the codebook HTML
# Handles all NHANES page variants (extra attrs on <a>, lowercase anchors,
# old/new <h3> formats)
# ---------------------------------------------------------------------------

def regex_extract_variables(html):
    # Build ordered variable list from nav links
    nav = re.findall(
        r'<a\s[^>]*href=["\']#([A-Za-z][A-Za-z0-9_]*)["\'][^>]*>'
        r'\s*([A-Z][A-Z0-9_]+)\s*-\s*([^<]+?)\s*</a>',
        html
    )
    seen, variables = set(), []
    for _anchor, name, label in nav:
        name = name.strip().upper()
        if name not in seen and label.strip():
            seen.add(name)
            variables.append({
                "name":         name,
                "label":        label.strip(),
                "english_text": None,
                "target":       None,
                "count":        None,
                "values":       [],
            })
    if not variables:
        return []

    # Split page into per-variable sections
    sections = re.split(r'<h3[^>]*class=["\']vartitle["\'][^>]*>', html)
    if len(sections) <= 1:
        # Fallback for older page structures
        sections = re.split(r'<h3[^>]*id=["\'][A-Z][A-Z0-9_]+["\'][^>]*>', html)

    var_map = {v["name"]: v for v in variables}

    for sec in sections[1:]:
        m = re.match(r'\s*([A-Z][A-Z0-9_]+)\s*-', sec)
        if not m or m.group(1) not in var_map:
            continue
        var = var_map[m.group(1)]

        # English Text
        eng = re.search(
            r'<dt>\s*English Text:\s*</dt>\s*<dd[^>]*>(.*?)</dd>',
            sec, re.DOTALL | re.I
        )
        if eng:
            var["english_text"] = re.sub(r'<[^>]+>', '', eng.group(1)).strip()

        # Target population
        tgt = re.search(
            r'<dt>\s*Target:\s*</dt>\s*<dd[^>]*>(.*?)</dd>',
            sec, re.DOTALL | re.I
        )
        if tgt:
            var["target"] = re.sub(r'<[^>]+>', '', tgt.group(1)).strip()

        # Values table
        tbl = re.search(
            r'<table[^>]*class=["\']values["\'][^>]*>(.*?)</table>',
            sec, re.DOTALL | re.I
        )
        if not tbl:
            continue

        rows = re.findall(
            r'<tr[^>]*>.*?<td[^>]*class=["\']values["\'][^>]*>(.*?)</td>'
            r'.*?<td[^>]*class=["\']values["\'][^>]*>(.*?)</td>'
            r'.*?<td[^>]*align=["\']right["\'][^>]*>\s*([\d,]+)\s*</td>',
            tbl.group(1), re.DOTALL | re.I
        )

        total, vals = 0, []
        for code, desc, cnt in rows:
            code = re.sub(r'<[^>]+>', '', code).strip()
            desc = re.sub(r'<[^>]+>', '', desc).strip()
            n    = int(cnt.replace(',', ''))
            if code != '.' and desc.lower() != 'missing':
                total += n
            vals.append({"code": code, "desc": desc, "count": n})

        var["count"]  = total
        var["values"] = vals

    return variables


# ---------------------------------------------------------------------------
# Step 3a — Regex: extract last updated date
# ---------------------------------------------------------------------------

def regex_extract_last_updated(html):
    patterns = [
        r'Last\s+(?:Revised|Updated)[:\s]*</[^>]+>\s*<[^>]+>([^<]+)<',
        r'Last\s+(?:Revised|Updated)[:\s]*([A-Z][a-z]+ \d{4})',
        r'Last\s+(?:Revised|Updated)[:\s]*(\w[\w\s,]+\d{4})',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val.lower() not in ('na', 'n/a', ''):
                return val
    return None


# ---------------------------------------------------------------------------
# NIM helpers
# ---------------------------------------------------------------------------

def nim_chat(messages, max_tokens=4096):
    if not NIM_API_KEY:
        raise RuntimeError("NIM_API_KEY not set in .env")
    payload = json.dumps({
        "model":       NIM_MODEL,
        "messages":    messages,
        "max_tokens":  max_tokens,
        "temperature": 0.0,
    }).encode()
    req = urllib.request.Request(
        f"{NIM_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {NIM_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def safe_json(text, default):
    text = re.sub(r'^```[a-z]*\n?', '', text.strip(), flags=re.I)
    text = re.sub(r'\n?```$', '', text.strip())
    try:
        return json.loads(text)
    except Exception:
        for ch in ('[', '{'):
            i = text.find(ch)
            if i != -1:
                try:    return json.loads(text[i:])
                except: pass
    return default


# ---------------------------------------------------------------------------
# Step 3b — NIM: get last_updated when regex fails
# ---------------------------------------------------------------------------

def nim_extract_last_updated(html):
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()[:8000]
    reply = nim_chat([
        {"role": "system", "content": SYSTEM_LAST_UPDATED},
        {"role": "user",   "content": (
            "From the text below find when this dataset was last revised or updated.\n"
            'Return JSON: {"last_updated": "Month YYYY"} or {"last_updated": null}.\n\n'
            "TEXT:\n" + text
        )},
    ], max_tokens=100)
    return safe_json(reply, default={}).get("last_updated")


# ---------------------------------------------------------------------------
# Step 3c — NIM: extract card info for data.js
# (name, desc, rows, source, subtypes, tasks)
# ---------------------------------------------------------------------------

def nim_extract_card_info(html, ds_id, url):
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()[:8000]
    reply = nim_chat([
        {"role": "system", "content": SYSTEM_CARD_INFO},
        {"role": "user",   "content": (
            "From the text below extract dataset info. Return JSON with these keys:\n"
            "  name     – short descriptive name (e.g. 'NHANES Demographics 2015-16')\n"
            "  desc     – one sentence description of what this dataset contains\n"
            "  rows     – approximate number of records as a string (e.g. '9,971') or null\n"
            "  source   – organisation or study name (e.g. 'NHANES', 'MIMIC-IV')\n"
            "  subtypes – array, pick from: demographics, dietary, laboratory, examination,\n"
            "             questionnaire, ehr, chest-xray, ct-scan, mri, clinical-notes, ecg, vitals\n"
            "  tasks    – array, pick from: classification, regression, clustering,\n"
            "             nlp, detection, segmentation, survival, prediction\n\n"
            "TEXT:\n" + text
        )},
    ], max_tokens=300)
    result         = safe_json(reply, default={})
    result["id"]     = ds_id
    result["docUrl"] = url
    return result


# ---------------------------------------------------------------------------
# Step 4a — NIM: enrich variables with data_type / unit / notes
# ---------------------------------------------------------------------------

def nim_enrich_variables(variables):
    enriched = []
    total_batches = (len(variables) + NIM_ENRICH_BATCH - 1) // NIM_ENRICH_BATCH

    for i in range(0, len(variables), NIM_ENRICH_BATCH):
        batch      = variables[i:i + NIM_ENRICH_BATCH]
        batch_num  = i // NIM_ENRICH_BATCH + 1
        print(f"      Batch {batch_num}/{total_batches} ({len(batch)} variables)...")

        slim = [
            {
                "name":         v["name"],
                "label":        v["label"],
                "english_text": v.get("english_text"),
                "values":       v.get("values", [])[:8],
            }
            for v in batch
        ]

        reply = nim_chat([
            {"role": "system", "content": SYSTEM_ENRICH},
            {"role": "user",   "content": (
                "For each variable below add exactly 3 keys and return the SAME array:\n"
                "  data_type – Continuous | Categorical | Binary | Ordinal | "
                "Identifier | Weight/Design | Date/Time\n"
                "  unit      – physical unit string or null\n"
                "  notes     – 1-2 sentence analyst tip or null\n"
                "Same order, no extra keys.\n\nVARIABLES:\n"
                + json.dumps(slim, ensure_ascii=False)
            )},
        ])

        result = safe_json(reply, default=[])
        if isinstance(result, list) and len(result) == len(batch):
            for orig, r in zip(batch, result):
                orig["data_type"] = r.get("data_type", "—")
                orig["unit"]      = r.get("unit")
                orig["notes"]     = r.get("notes")
                enriched.append(orig)
        else:
            # NIM response malformed — keep variables without enrichment
            print(f"      Warning: batch {batch_num} enrichment failed, skipping NIM fields.")
            for v in batch:
                v.setdefault("data_type", "—")
                v.setdefault("unit",      None)
                v.setdefault("notes",     None)
                enriched.append(v)

    return enriched


# ---------------------------------------------------------------------------
# Step 4b — Build review page (left: original, right: extracted)
# ---------------------------------------------------------------------------

def build_review_page(ds_id, url, variables, last_updated, expected_count, output_path):
    if expected_count is None:
        status, msg = "warn", "Could not verify variable count"
    elif len(variables) == expected_count:
        status, msg = "ok", f"Count matches: {len(variables)} / {expected_count}"
    else:
        status, msg = "error", (
            f"MISMATCH — extracted {len(variables)}, "
            f"expected {expected_count} (missing {expected_count - len(variables)})"
        )

    rows = ""
    for v in variables:
        vals_preview = "<br>".join(
            f"<code>{x['code']}</code>&nbsp;{x['desc']}&nbsp;(n={x['count']:,})"
            for x in v.get("values", [])[:6]
        )
        if len(v.get("values", [])) > 6:
            vals_preview += f"<br><span style='color:var(--text3)'>+{len(v['values'])-6} more</span>"

        type_cls = {
            "Continuous":    "tb-f",
            "Categorical":   "tb-c",
            "Binary":        "tb-c",
            "Ordinal":       "tb-c",
            "Identifier":    "tb-i",
            "Weight/Design": "tb-i",
        }.get(v.get("data_type",""), "tb-i")

        rows += (
            f"<tr>"
            f"<td style='font-family:monospace;font-weight:500;white-space:nowrap'>{v['name']}</td>"
            f"<td><strong>{v.get('label') or '—'}</strong>"
            f"<br><span style='color:var(--text3);font-size:11px'>{v.get('english_text') or ''}</span></td>"
            f"<td style='color:var(--text2)'>{v.get('target') or '—'}</td>"
            f"<td style='font-size:11px'>{vals_preview or '—'}</td>"
            f"<td><span class='tb {type_cls}'>{v.get('data_type') or '—'}</span></td>"
            f"<td style='color:var(--text2)'>{v.get('unit') or '—'}</td>"
            f"<td style='color:var(--text3);font-size:11px;font-style:italic'>{v.get('notes') or '—'}</td>"
            f"</tr>"
        )

    status_style = {
        "ok":    "background:#E1F5EE;color:#0F6E56",
        "error": "background:#FAECE7;color:#712B13",
        "warn":  "background:#FAEEDA;color:#633806",
    }[status]

    short_url = url[:70] + ("..." if len(url) > 70 else "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Review: {ds_id}</title>
<link rel="stylesheet" href="style.css">
<style>
  body {{ padding: 0; }}
  /* Top bar */
  .review-bar {{
    position: sticky; top: 0; z-index: 50;
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 24px;
    background: var(--bg);
    border-bottom: 0.5px solid var(--border);
  }}
  .review-bar-left {{ display: flex; align-items: center; gap: 12px; }}
  .review-badge {{
    font-size: 10px; font-weight: 600; letter-spacing: .06em;
    text-transform: uppercase; padding: 3px 9px; border-radius: 20px;
    background: var(--bg3); color: var(--text2);
  }}
  .review-id {{ font-size: 14px; font-weight: 500; color: var(--text); }}
  .count-pill {{
    font-size: 11px; font-weight: 500; padding: 3px 10px;
    border-radius: 20px; {status_style}
  }}
  .review-bar-right {{ display: flex; align-items: center; gap: 16px; font-size: 12px; color: var(--text3); }}
  .review-bar-right a {{ color: #378ADD; text-decoration: none; }}
  /* Split layout */
  .split {{ display: flex; height: calc(100vh - 45px); overflow: hidden; }}
  .left-pane {{
    flex: 1.1; border-right: 0.5px solid var(--border);
    display: flex; flex-direction: column;
  }}
  .pane-label {{
    padding: 7px 14px; font-size: 10px; font-weight: 500; letter-spacing: .07em;
    text-transform: uppercase; color: var(--text3);
    border-bottom: 0.5px solid var(--border);
    background: var(--bg2);
    display: flex; align-items: center; justify-content: space-between;
  }}
  .pane-label a {{ font-size: 11px; color: #378ADD; text-decoration: none; text-transform: none; letter-spacing: 0; }}
  iframe {{ flex: 1; border: none; width: 100%; }}
  .right-pane {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
  .right-pane-inner {{ flex: 1; overflow-y: auto; padding: 0 }}
  /* Search */
  .tbl-toolbar {{
    display: flex; align-items: center; gap: 10px;
    padding: 8px 14px; border-bottom: 0.5px solid var(--border);
    background: var(--bg2);
  }}
  .tbl-search {{
    flex: 1; max-width: 280px;
    padding: 5px 10px; border: 0.5px solid var(--border);
    border-radius: 6px; font-size: 12px;
    background: var(--bg); color: var(--text); outline: none;
  }}
  .tbl-search:focus {{ border-color: #378ADD; }}
  .var-count {{ font-size: 11px; color: var(--text3); }}
  /* Table */
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  thead th {{
    position: sticky; top: 0; z-index: 5;
    padding: 7px 10px; text-align: left;
    font-size: 10px; font-weight: 500; letter-spacing: .06em;
    text-transform: uppercase; color: var(--text2);
    background: var(--bg2); border-bottom: 0.5px solid var(--border);
    white-space: nowrap;
  }}
  tbody tr {{ border-bottom: 0.5px solid var(--border); }}
  tbody tr:hover {{ background: var(--bg2); }}
  td {{ padding: 7px 10px; vertical-align: top; line-height: 1.5; }}
  code {{
    background: var(--bg3); padding: 1px 4px;
    border-radius: 3px; font-size: 10px; color: var(--text2);
  }}
</style>
</head>
<body>

<div class="review-bar">
  <div class="review-bar-left">
    <span class="review-badge">Review</span>
    <span class="review-id">{ds_id}</span>
    <span class="count-pill">{msg}</span>
  </div>
  <div class="review-bar-right">
    <span>Last Updated: <strong style="color:var(--text)">{last_updated or 'not found'}</strong></span>
    <a href="{url}" target="_blank">{short_url} ↗</a>
  </div>
</div>

<div class="split">
  <div class="left-pane">
    <div class="pane-label">
      Original documentation page
      <a href="{url}" target="_blank">open in new tab ↗</a>
    </div>
    <iframe src="{url}"></iframe>
  </div>

  <div class="right-pane">
    <div class="tbl-toolbar">
      <input class="tbl-search" id="srch" placeholder="Filter variables…"
             oninput="filterTable(this.value)">
      <span class="var-count">{len(variables)} variables extracted</span>
    </div>
    <div class="right-pane-inner">
      <table id="vtbl">
        <thead>
          <tr>
            <th>Variable</th>
            <th>Label / English Text</th>
            <th>Target</th>
            <th>Values</th>
            <th>Type</th>
            <th>Unit</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>
</div>

<script>
  function filterTable(q) {{
    q = q.toLowerCase();
    document.querySelectorAll('#vtbl tbody tr').forEach(function(tr) {{
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
  }}
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

# ---------------------------------------------------------------------------
# Step 5 — Update data.js from all datasets currently in schema.json
# Preserves the SUBTYPE_TAG and TASK_TAG blocks from the original data.js
# ---------------------------------------------------------------------------

def update_data_js(all_results, new_card, data_js_path):
    # Read existing data.js to preserve SUBTYPE_TAG / TASK_TAG
    tail = ""
    if os.path.exists(data_js_path):
        existing = open(data_js_path).read()
        m = re.search(r'const SUBTYPE_TAG', existing)
        if m:
            tail = existing[m.start():]

    # If data.js doesn't exist yet, copy tail from the original nhanes-explorer-new
    if not tail:
        original = os.path.expanduser(
            "~/Desktop/nhanes-explorer-new/data.js"
        )
        if os.path.exists(original):
            src = open(original).read()
            m   = re.search(r'const SUBTYPE_TAG', src)
            if m:
                tail = src[m.start():]

    # Build DATASETS array — one entry per dataset in schema.json
    ds_lines = "const DATASETS = [\n"
    for did, ddata in all_results.items():
        if did == new_card.get("id"):
            c = new_card
        else:
            # Re-use whatever is already stored in schema.json
            c = {
                "id":       did,
                "name":     ddata.get("name", did),
                "desc":     ddata.get("desc", ""),
                "rows":     str(ddata.get("variable_count", "")),
                "source":   ddata.get("source", ""),
                "subtypes": ddata.get("subtypes", []),
                "tasks":    ddata.get("tasks", []),
                "docUrl":   ddata.get("url", ""),
                "last_updated": ddata.get("last_updated", ""),
            }

        c_id      = c.get("id", "")
        c_name    = c.get("name", "").replace("'", "\\'")
        c_desc    = c.get("desc", "").replace("'", "\\'")
        c_source  = c.get("source", "").replace("'", "\\'")
        c_rows    = str(c.get("rows", "") or "")
        c_docUrl  = c.get("docUrl", "")
        c_updated = str(c.get("last_updated", "") or "")
        c_sub     = json.dumps(c.get("subtypes") or [])
        c_tasks   = json.dumps(c.get("tasks") or [])

        ds_lines += (
            f"  {{\n"
            f"    id: '{c_id}',\n"
            f"    name: '{c_name}',\n"
            f"    desc: '{c_desc}',\n"
            f"    subtypes: {c_sub},\n"
            f"    tasks: {c_tasks},\n"
            f"    source: '{c_source}',\n"
            f"    rows: '{c_rows}',\n"
            f"    docUrl: '{c_docUrl}',\n"
            f"    last_updated: '{c_updated}'\n"
            f"  }},\n"
        )
    ds_lines += "];\n\n"

    content = (
        "const PROXY   = 'http://localhost:8765/';\n"
        "const API_URL = 'http://localhost:8765/api/extract';\n\n"
        + ds_lines
        + tail
    )

    with open(data_js_path, "w") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Main — run one URL at a time
# Usage: python3 extractor.py <url> [dataset-id]
# ---------------------------------------------------------------------------

def main():
    if not NIM_API_KEY:
        print("ERROR: NIM_API_KEY not set in .env")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage:   python3 extractor.py <url> [dataset-id]")
        print("Example: python3 extractor.py \\")
        print("  https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/DEMO_I.htm \\")
        print("  nhanes-demo-2015")
        sys.exit(1)

    url   = sys.argv[1].strip()
    ds_id = (sys.argv[2].strip() if len(sys.argv) > 2
             else url.split("/")[-1].replace(".htm", "").replace(".html", ""))

    print(f"\nProcessing : {ds_id}")
    print(f"URL        : {url}\n")

    # Step 1: Fetch
    print("[1/4] Fetching HTML...")
    html = fetch_html(url)
    print(f"      {len(html):,} chars downloaded")

    # Step 2: Regex extract variables
    print("[2/4] Regex extraction...")
    variables      = regex_extract_variables(html)
    expected_count = len(variables)
    print(f"      {expected_count} variables found")

    # Step 3: Last updated
    print("[3/4] Extracting last updated date...")
    last_updated = fetch_last_modified(url)
    if not last_updated:
        print("      HTTP header empty, trying page content...")
        last_updated = regex_extract_last_updated(html)
    if not last_updated:
        print("      Regex found nothing, asking NIM...")
        last_updated = nim_extract_last_updated(html)

    # Step 4: NIM enrich variables
    print("[4/4] NIM enrichment...")
    variables = nim_enrich_variables(variables)

    if len(variables) != expected_count:
        print(f"      WARNING: count changed after enrichment "
              f"({len(variables)} vs {expected_count})")

    # Open review page — let the user verify before saving
    review_path = os.path.abspath(f"review_{ds_id}.html")
    build_review_page(ds_id, url, variables, last_updated, expected_count, review_path)
    webbrowser.open(f"file://{review_path}")
    print(f"\nReview page opened in browser.")
    print("Left side = original documentation page")
    print("Right side = what NIM extracted\n")

    confirm = input("Save to schema.json and data.js? (y/n): ").strip().lower()
    if confirm != "y":
        print("Not saved. Run again when ready.")
        sys.exit(0)

    # Load existing schema.json
    schema_path  = "schema.json"
    data_js_path = "data.js"
    all_results  = {}
    if os.path.exists(schema_path):
        with open(schema_path) as f:
            all_results = json.load(f)

    # Extract card info for data.js
    print("\nExtracting card info for data.js...")
    card = nim_extract_card_info(html, ds_id, url)
    card["last_updated"] = last_updated

    # Save to schema.json
    all_results[ds_id] = {
        "name":           card.get("name", ds_id),
        "desc":           card.get("desc", ""),
        "source":         card.get("source", ""),
        "subtypes":       card.get("subtypes", []),
        "tasks":          card.get("tasks", []),
        "url":            url,
        "last_updated":   last_updated,
        "variable_count": len(variables),
        "variables":      variables,
    }

    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"schema.json updated ({len(all_results)} datasets total)")

    # Rebuild data.js
    update_data_js(all_results, card, data_js_path)
    print(f"data.js updated ({len(all_results)} datasets total)")

    print(f"\nDone! Next step: run python3 proxy.py then open index.html")


if __name__ == "__main__":
    main()