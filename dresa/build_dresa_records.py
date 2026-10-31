"""Build DReSA catalogue metadata records for AAAIR outputs.

Fills one copy of the DReSA training materials template per record (R0 to R5,
plus optional R6+ records for Australian courses) and writes a summary workbook.
Narrative field values live in records.yaml; counts and lists are harvested from
the WP2, WP3&4 and WP6 source files in this repository.

Usage:
    python build_dresa_records.py --template TEMPLATE.docx --out OUT_DIR
        [--check-dresa] [--au-records]

--check-dresa  query the public DReSA API for Australian course titles already listed
--au-records   also write R6+ records for candidates marked "Separate record"
"""

import argparse
import collections
import copy
import datetime
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import docx
import openpyxl
import yaml
from docx.enum.text import WD_BREAK
from docx.shared import Emu, Pt, Twips

REPO = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent

WP2_DATAJS = REPO / "WP2" / "data.js"
TOOLS_XLSX = next((REPO / "WP3&4").rglob("Alltogethertoolsnoborrar.xlsx"))
COURSES_XLSX = next((REPO / "WP6").rglob("WP6.2_database_1_30.06.26.xlsx"))

# Field order as it appears in the three template tables.
TABLE_FIELDS = [
    ["Title", "Description", "Keywords", "URL", "Licence", "Status", "Contact"],
    ["DOI", "Version", "Content provider", "Authors", "Contributors", "Events",
     "Target audiences", "Prerequisites", "Competency level", "Learning objectives",
     "Date created"],
    ["Fields of research", "Date modified", "Date published", "Resource types",
     "Other types", "Subsets", "Syllabus", "External resources"],
]
ALL_FIELDS = [f for t in TABLE_FIELDS for f in t]

SOURCE_INFO = {
    "NHANES": ("US National Health and Nutrition Examination Survey (CDC)", "Person-level survey",
               "US public-use data [To confirm]"),
    "PHIDU": ("Social Health Atlas of Australia, PHIDU, Torrens University Australia",
              "Regional aggregate statistics", "CC BY-NC-SA 3.0 AU"),
    "MIMIC-IV": ("MIMIC-IV and MIMIC-IV-ED electronic health records (MIT LCP, PhysioNet)",
                 "Person-level clinical (pointer records only)", "Credentialed access; not redistributed"),
    "PTB-XL": ("PTB-XL 12-lead ECG dataset (PhysioNet)", "Person-level clinical",
               "CC BY 4.0 (confirmed on PhysioNet)"),
}
SUBTYPE_LABEL = {
    "laboratory": "Laboratory", "questionnaire": "Questionnaire and lifestyle",
    "health-status": "Population health status", "social-determinants": "Social determinants of health",
    "examination": "Physical examination", "health-services": "Health services use",
    "dietary": "Diet and nutrition", "indigenous-health": "Indigenous health",
    "ehr": "Clinical electronic health records", "demographics": "Demographics",
    "ecg": "ECG (physiological signals)",
}
COST_RANK = {"Free": 0, "Free to audit": 1, "Subscription": 2, "Paid": 3}
RELEVANCE_RANK = {"Yes - High": 0, "Yes - Moderate": 1, "Yes - Low": 2}
HEALTH_RANK = {"yes - high": 0, "yes - medium": 1, "yes - low": 2}
FEATURED_PER_DOMAIN = 4
TABLE_WIDTH = Twips(10000)  # matches the template's fixed table width


def clean(text):
    """Normalise text for output: no em dashes, collapse whitespace."""
    if text is None:
        return ""
    text = str(text).replace("—", " - ").replace("–", "-")
    return re.sub(r"[ \t]+", " ", text).strip()


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def git_dates(path=None):
    cmd = ["log", "--format=%ad", "--date=short"] + (["--", path] if path else [])
    dates = sorted(git(*cmd).split())
    return dates[0], dates[-1]


def first_url(text):
    m = re.search(r"https?://[^\s,;)]+", str(text or ""))
    return m.group(0).rstrip(".") if m else ""


# ---------------------------------------------------------------------------
# Harvesting


def load_datasets():
    text = WP2_DATAJS.read_text(encoding="utf-8")
    start = text.index("[")
    end = text.index("\n];") + 2
    return json.loads(text[start:end])


def load_tools(cfg):
    ws = openpyxl.load_workbook(TOOLS_XLSX, read_only=True, data_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    by_name = {str(r[0]).strip().lower(): dict(zip(header, r)) for r in rows[1:] if r[0]}
    tools = []
    for t in cfg["tools"]:
        src = by_name.get(t["xlsx"].strip().lower())
        if src is None:
            sys.exit(f"Tool {t['xlsx']!r} not found in {TOOLS_XLSX.name}")
        # records.yaml may override the workbook's free-text licence and training columns.
        tools.append({
            **t,
            "licence": t.get("licence") or clean(re.sub(r"https?://\S+", "", str(src["license.type"] or "")))[:80],
            "home": first_url(src["home.page.url"]),
            "training": t.get("training") or first_url(src["training"]) or first_url(src["manuals"]),
            "containers": clean(re.sub(r"https?://\S+", "", str(src["cointainerisable"] or "")))[:60],
        })
    return tools


def norm_status(value):
    return clean(value).lower()


def is_async(c):
    return (c["learning_pace"] == "Self-paced" and c["delivery_platform"] == "Online"
            and c["format"] not in ("Workshop", "Webinar")
            and not norm_status(c["enrolment_status"]).startswith(("scheduled", "one-time")))


def load_courses():
    wb = openpyxl.load_workbook(COURSES_XLSX, read_only=True, data_only=True)
    rows = list(wb["coursework_resources"].iter_rows(values_only=True))
    courses = [dict(zip(rows[0], r)) for r in rows[1:] if any(r)]
    selected = [c for c in courses if c["select_reject"] == "select"]
    domains = collections.defaultdict(set)
    for course_id, _tool, domain in list(wb["course_tools"].iter_rows(values_only=True))[1:]:
        if course_id and domain:
            domains[course_id].add(domain)
    for c in selected:
        c["domains"] = sorted(domains.get(c["course_id"], ()))
        c["async"] = is_async(c)
    return selected


def featured_courses(selected):
    """Pick up to FEATURED_PER_DOMAIN self-paced courses per domain, spread across providers."""
    def key(c):
        return (RELEVANCE_RANK.get(c["research_workflow_relevance"], 9),
                HEALTH_RANK.get(clean(c["health_domain_relevance"]).lower(), 9),
                COST_RANK.get(c["cost_model"], 9), clean(c["course_name"]))

    pool = [c for c in selected if c["async"] and c["no_longer_maintained"] != "Yes"
            and c["cost_model"] in COST_RANK]
    domain_names = sorted({d for c in selected for d in c["domains"]})
    picked, used = {}, set()
    for domain in domain_names:
        providers, chosen = set(), []
        for c in sorted((c for c in pool if domain in c["domains"]), key=key):
            provider = re.split(r"[/(]", str(c["provider"]))[0].strip().lower()
            if c["course_id"] in used or provider in providers:
                continue
            chosen.append(c)
            used.add(c["course_id"])
            providers.add(provider)
            if len(chosen) == FEATURED_PER_DOMAIN:
                break
        picked[domain] = chosen
    return picked


def au_candidates(selected):
    """Australian courses that are self-paced, or scheduled and not a past one-off event."""
    out = []
    for c in selected:
        if c["country"] != "Australia" or c["no_longer_maintained"] == "Yes":
            continue
        status = norm_status(c["enrolment_status"])
        if c["async"]:
            reason = "Self-paced online"
        elif status != "one-time event - passed":
            reason = f"Scheduled or recurring ({clean(c['enrolment_status']) or 'status not stated'})"
        else:
            continue
        marketplace = "udemy" in str(c["provider"]).lower()
        if c["async"] and not marketplace:
            proposed = "Separate record"
        elif not c["async"] and status in ("scheduled cohort - open", "open enrolment", "open"):
            proposed = "Separate record"
        else:
            proposed = "Course Finder aggregate only"
        note = "Marketplace course; owner is the instructor, not an Australian provider" if marketplace else ""
        out.append({"course": c, "reason": reason, "proposed": proposed, "note": note, "dresa": ""})
    # The same course is sometimes listed once per session or per co-provider; keep the first.
    seen = {}
    for cand in out:
        name = re.sub(r"\W+", " ", clean(cand["course"]["course_name"]).lower()).strip()
        if cand["proposed"] == "Separate record" and name in seen:
            cand["proposed"] = "Duplicate session"
            cand["note"] = f"Same course as: {seen[name]}"
        elif cand["proposed"] == "Separate record":
            seen[name] = f"{clean(cand['course']['course_name'])} ({clean(cand['course']['provider'])})"
    return out


def dresa_titles(kind, query):
    url = f"https://dresa.org.au/{kind}.json?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "AAAIR-dresa-check/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return [h.get("title", "") for h in json.load(resp)]


def check_dresa(candidates):
    """Look for each candidate title among DReSA materials and events (read-only public API)."""
    for cand in candidates:
        title = clean(cand["course"]["course_name"])
        core = re.sub(r"^(WORKSHOP|WEBINAR):\s*", "", title, flags=re.I).lower()
        try:
            hits = [("material", t) for t in dresa_titles("materials", title)]
            hits += [("event", t) for t in dresa_titles("events", title)]
        except Exception as exc:  # network errors are reported, not fatal
            cand["dresa"] = f"Check failed: {exc}"
            continue
        exact = [(k, t) for k, t in hits if core in clean(t).lower()]
        if exact:
            cand["dresa"] = f"Already in DReSA as {exact[0][0]}: {clean(exact[0][1])}"
            if cand["proposed"] == "Separate record":
                cand["proposed"] = "Already in DReSA"
        else:
            cand["dresa"] = f"Not found ({len(hits)} loose matches)"


# ---------------------------------------------------------------------------
# Document writing


def set_cell(cell, text, bold=False, size=None):
    cell.text = ""
    lines = clean(text).split("\n") if text else [""]
    par = cell.paragraphs[0]
    for i, line in enumerate(lines):
        run = par.add_run(line)
        run.bold = bold
        if size:
            run.font.size = Pt(size)
        if i < len(lines) - 1:
            run.add_break(WD_BREAK.LINE)


def set_widths(table, widths):
    """Set cell and grid widths; the template tables use a fixed layout, so both matter."""
    for row in table.rows:
        for cell, w in zip(row.cells, widths):
            cell.width = Emu(w)
    for col, w in zip(table._tbl.tblGrid.gridCol_lst, widths):
        col.w = Emu(w)


def add_table(doc, header, rows, widths):
    table = doc.add_table(rows=1, cols=len(header))
    # Reuse the template's table look (light borders, fixed layout) rather than a named style.
    table._tbl.remove(table._tbl.tblPr)
    table._tbl.insert(0, copy.deepcopy(doc.tables[0]._tbl.tblPr))
    for cell, text in zip(table.rows[0].cells, header):
        set_cell(cell, text, bold=True, size=9)
    for r in rows:
        cells = table.add_row().cells
        for cell, text in zip(cells, r):
            set_cell(cell, str(text), size=9)
    set_widths(table, widths)
    doc.add_paragraph()
    return table


def build_doc(template, record, breakdown, today):
    doc = docx.Document(template)
    body_width = TABLE_WIDTH
    paras = doc.paragraphs
    paras[0].text = f"DReSA catalogue record {record['id']}: {clean(record['Title'])}"
    paras[1].text = (f"Prepared from the AAAIR repository (github.com/gnanabharathy/AAAIR) on {today}, "
                     "using the DReSA training materials submission template. Values marked [To confirm] "
                     "or [Drafted] need checking before submission to https://dresa.org.au/materials/new.")
    paras[3].text = ""
    widths = [int(body_width * 0.18), int(body_width * 0.27), int(body_width * 0.55)]
    for table, fields in zip(doc.tables, TABLE_FIELDS):
        table.add_column(Emu(widths[2]))
        set_cell(table.rows[0].cells[2], "Response", bold=True)
        for row in table.rows[1:]:
            field = row.cells[0].text.strip()
            if field not in fields:
                sys.exit(f"Unexpected template field {field!r}")
            set_cell(row.cells[2], record.get(field, ""))
        set_widths(table, widths)
    for title, header, rows, fractions in breakdown:
        doc.add_heading(title, level=1)
        add_table(doc, header, rows, [int(body_width * f) for f in fractions])
    return doc


# ---------------------------------------------------------------------------
# Breakdown tables per record


def breakdowns(kind, ctx, cfg):
    if kind == "components":
        return [("Components of the hub", ["Record", "Work package", "What it offers"], [
            ["R1 Open Healthcare Dataset Explorer and Quality Check", "WP2",
             f"{ctx['n_entries']:,} open health dataset entries, grouped by source and domain, with data quality and FAIR checks"],
            ["R2 Recommended Analytics and AI Tools for Health Research", "WP3 and WP4",
             f"Directory of {ctx['n_tools']} tools in {ctx['n_tool_cats']} categories, with training links"],
            ["R3 Ethics and Governance Matrix and Checklist", "WP5",
             "Six recommendations and a 41-instrument matrix in four tiers"],
            ["R4 Health Research Analytics and AI Course Finder", "WP6.4",
             f"{ctx['n_selected']} curated courses; {ctx['n_async']} self-paced"],
            ["R5 Training Needs and Priority Tool Training Recommendations", "WP6.1 to WP6.3, WP6.5",
             "Survey of 99 researchers and gap analysis for 11 priority tools"],
        ], [0.38, 0.17, 0.45])]

    if kind == "datasets":
        src_rows = [[s, SOURCE_INFO[s][0], f"{n:,}", SOURCE_INFO[s][1], SOURCE_INFO[s][2]]
                    for s, n in ctx["by_source"].most_common()]
        dom_rows = [[SUBTYPE_LABEL.get(sub, sub), src, f"{n:,}"] for (src, sub), n in ctx["by_domain"].most_common()]
        task_rows = [[t.replace("-", " ").capitalize(), f"{n:,}"] for t, n in ctx["by_task"].most_common()]
        return [
            ("Data categories by source", ["Source", "Description", "Entries", "Level of data", "Upstream licence"],
             src_rows, [0.12, 0.36, 0.1, 0.2, 0.22]),
            ("Data categories by domain", ["Domain", "Source", "Entries"], dom_rows, [0.5, 0.3, 0.2]),
            ("Machine learning task tags", ["Task", "Entries (an entry can have several)"], task_rows, [0.5, 0.5]),
        ]

    if kind == "tools":
        tables = []
        for cat in cfg["tool_categories"]:
            rows = [[t["name"], t["tier"], t["desc"], t["licence"], t["home"], t["training"] or "See home page"]
                    for t in ctx["tools"] if t["category"] == cat]
            if rows:
                tables.append((cat, ["Tool", "Tier", "Description", "Licence", "Home page", "Training"],
                               rows, [0.13, 0.08, 0.33, 0.14, 0.16, 0.16]))
        tables.append(("Tools assessed but not recommended", ["Note"], [[cfg["tools_not_recommended"]]], [1.0]))
        return tables

    if kind == "ethics":
        return [
            ("Checklist: six recommendations", ["#", "Recommendation"],
             [[i + 1, r] for i, r in enumerate(cfg["ethics_recommendations"])], [0.08, 0.92]),
            ("Ethics and Governance Matrix tiers", ["Tier", "Scope", "Instruments"], cfg["ethics_tiers"],
             [0.15, 0.65, 0.2]),
            ("Licensing key used in the matrix", ["Key"], [[cfg["ethics_licensing_key"]]], [1.0]),
        ]

    if kind == "courses":
        feat_rows = [[d, clean(c["course_name"]), clean(c["provider"]), clean(c["level"]),
                      clean(c["cost_model"]), clean(c["link"])]
                     for d, cs in ctx["featured"].items() for c in cs]
        agg = ctx["sched_summary"]
        return [
            ("Featured self-paced courses by domain",
             ["Domain", "Course", "Provider", "Level", "Cost", "Link"], feat_rows,
             [0.16, 0.26, 0.16, 0.1, 0.1, 0.22]),
            ("Self-paced courses at a glance", ["Measure", "Breakdown"], ctx["async_summary"], [0.25, 0.75]),
            ("Scheduled, instructor-led and one-off offerings (summary only)", ["Measure", "Breakdown"], agg,
             [0.25, 0.75]),
            ("Providers with three or more scheduled offerings", ["Provider", "Scheduled offerings in the database"],
             ctx["recurring_providers"], [0.6, 0.4]),
        ]

    if kind == "needs":
        return [("Priority tools and recommendations", ["Priority tool (WP6.1 survey)", "Recommendation"],
                 cfg["priority_tools"], [0.5, 0.5])]
    return []


def count_line(counter, limit=None):
    return "; ".join(f"{clean(k) or 'Not stated'} {v}" for k, v in counter.most_common(limit))


# ---------------------------------------------------------------------------
# Australian course records (R6+)


def au_record(cand, index, cfg):
    c = cand["course"]
    parts = [f"{clean(c['course_name'])} is a {clean(c['format']).lower() or 'course'} from {clean(c['provider'])}."]
    if c["key_topics"]:
        parts.append(f"Topics: {clean(c['key_topics'])}.")
    parts.append(f"Delivery: {clean(c['delivery_platform'])}, {clean(c['learning_pace']).lower()}."
                 + (f" Duration: {clean(c['duration'])}." if c["duration"] else "")
                 + (f" Cost: {clean(c['cost_model'])}." if c["cost_model"] else ""))
    if c["access_notes"]:
        parts.append(clean(c["access_notes"]))
    level = clean(c["level"])
    return {
        "id": f"R{index}",
        "file": f"R{index}_AU_" + re.sub(r"[^A-Za-z0-9]+", "_", clean(c["course_name"]))[:60].strip("_"),
        "Title": clean(c["course_name"]),
        "Description": " ".join(parts),
        "Keywords": "; ".join(x for x in [clean(c["primary_tools"]), "; ".join(c["domains"])] if x),
        "URL": clean(c["link"]),
        "Licence": "Set by the provider [To confirm]",
        "Status": "Active [To confirm with provider]",
        "Contact": f"{clean(c['provider'])} [To confirm contact address]",
        "DOI": "Not known",
        "Version": "Not stated",
        "Content provider": clean(c["provider"]),
        "Authors": f"{clean(c['provider'])} [To confirm]",
        "Contributors": "Listed in the AAAIR Course Finder (record R4)",
        "Events": (f"Session listed when the database was compiled (30 June 2026): {clean(c['next_start_date'])}. "
                   "Check the provider for current dates.") if c["next_start_date"] else "Not applicable",
        "Target audiences": clean(c["target_audience"]) or "Researcher",
        "Prerequisites": clean(c["prerequisites"]) or "Not stated",
        "Competency level": level if level in ("Beginner", "Intermediate", "Advanced") else
        ("Advanced" if level == "Expert" else "Not specified"),
        "Learning objectives": "See the provider's course page [To confirm]",
        "Date created": "Not stated",
        "Fields of research": "4605 Data management and data science [To confirm]",
        "Date modified": "Not stated",
        "Date published": "Not yet published in DReSA",
        "Resource types": "Full course" if c["async"] else "Module",
        "Other types": clean(c["format"]),
        "Subsets": cfg["defaults"]["Subsets"],
        "Syllabus": clean(c["key_topics"]) or "See the provider's course page",
        "External resources": "Health Research Analytics and AI Course Finder (record R4)",
    }


# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--check-dresa", action="store_true")
    ap.add_argument("--au-records", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load((HERE / "records.yaml").read_text(encoding="utf-8"))
    today = datetime.date.today().isoformat()

    datasets = load_datasets()
    tools = load_tools(cfg)
    selected = load_courses()
    async_c = [c for c in selected if c["async"]]
    sched = [c for c in selected if not c["async"]]

    # Totals checked against the figures reported in the exploration of the source files.
    assert len(datasets) == 2589, len(datasets)
    assert len(selected) == 738, len(selected)
    assert len(async_c) == 565, len(async_c)

    ctx = {
        "n_entries": len(datasets),
        "by_source": collections.Counter(d["source"] for d in datasets),
        "by_domain": collections.Counter((d["source"], s) for d in datasets for s in d["subtypes"]),
        "by_task": collections.Counter(t for d in datasets for t in d["tasks"]),
        "tools": tools,
        "n_tools": len(tools),
        "n_tool_cats": len({t["category"] for t in tools}),
        "n_selected": len(selected),
        "n_providers": len({c["provider"] for c in selected}),
        "n_tools_taught": None,
        "n_async": len(async_c),
        "n_sched": len(sched),
        "n_sched_au": sum(c["country"] == "Australia" for c in sched),
        "featured": featured_courses(selected),
    }
    ctx["n_sources"] = len(ctx["by_source"])
    wb6 = openpyxl.load_workbook(COURSES_XLSX, read_only=True, data_only=True)
    sel_ids = {c["course_id"] for c in selected}
    ctx["n_tools_taught"] = len({t for cid, t, _ in list(wb6["course_tools"].iter_rows(values_only=True))[1:]
                                 if cid in sel_ids and t})
    ctx["async_summary"] = [
        ["Format", count_line(collections.Counter(c["format"] for c in async_c))],
        ["Cost", count_line(collections.Counter(c["cost_model"] for c in async_c))],
        ["Level", count_line(collections.Counter(c["level"] for c in async_c))],
        ["Domain (a course can be in several)", count_line(collections.Counter(d for c in async_c for d in c["domains"]))],
        ["Main providers", count_line(collections.Counter(c["provider"] for c in async_c), 12)],
        ["Australian providers", str(sum(c["country"] == "Australia" for c in async_c))],
    ]
    ctx["sched_summary"] = [
        ["Total", f"{len(sched)} offerings; browse them in the course finder rather than this record"],
        ["Australian or international", f"Australian {ctx['n_sched_au']}; international {len(sched) - ctx['n_sched_au']}"],
        ["Format", count_line(collections.Counter(c["format"] for c in sched))],
        ["Pace", count_line(collections.Counter(c["learning_pace"] for c in sched))],
        ["Enrolment status at 30 June 2026", count_line(collections.Counter(
            (clean(c["enrolment_status"]) or "Not stated").replace(" - ", ", ").capitalize() for c in sched))],
        ["Main providers", count_line(collections.Counter(c["provider"] for c in sched), 10)],
    ]
    ctx["recurring_providers"] = [[clean(p), n] for p, n in collections.Counter(
        c["provider"] for c in sched if norm_status(c["enrolment_status"]) != "one-time event - passed").most_common()
        if n >= 3]

    head, (first_all, last_all) = git("rev-parse", "--short", "HEAD"), git_dates()
    fmt = {
        **{k: v for k, v in ctx.items() if isinstance(v, int)},
        "git_head": head, "git_first_date": first_all, "git_last_date": last_all,
        "git_head_wp2": git("log", "-1", "--format=%h", "--", "WP2"),
    }
    for key, path in [("wp2", "WP2"), ("wp34", "WP3&4"), ("wp6", "WP6")]:
        fmt[f"git_first_date_{key}"], fmt[f"git_last_date_{key}"] = git_dates(path)

    records = []
    for raw in cfg["records"]:
        rec = {**cfg["defaults"], **raw}
        for field in ALL_FIELDS:
            rec[field] = clean(str(rec.get(field, "")).format(**fmt))
        records.append(rec)
        doc = build_doc(args.template, rec, breakdowns(rec["breakdown"], ctx, cfg), today)
        doc.save(args.out / f"{rec['file']}.docx")

    candidates = au_candidates(selected)
    if args.check_dresa:
        check_dresa(candidates)
    if args.au_records:
        n = 6
        for cand in candidates:
            if cand["proposed"] != "Separate record":
                continue
            rec = au_record(cand, n, cfg)
            cand["record"] = rec["id"]
            records.append(rec)
            build_doc(args.template, rec, [], today).save(args.out / f"{rec['file']}.docx")
            n += 1

    write_summary(args.out / "DReSA_Records_Summary.xlsx", records, tools, candidates, ctx)
    print(f"Wrote {len(records)} records to {args.out}")
    print(f"Australian course candidates: {len(candidates)} "
          f"({collections.Counter(c['proposed'] for c in candidates)})")


def write_summary(path, records, tools, candidates, ctx):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Records"
    ws.append(["Record", "File"] + ALL_FIELDS)
    for r in records:
        ws.append([r["id"], r["file"] + ".docx"] + [r.get(f, "") for f in ALL_FIELDS])
    ws = wb.create_sheet("Tool directory")
    ws.append(["Category", "Tool", "Tier", "Description", "Licence", "Container support", "Home page", "Training"])
    for t in tools:
        ws.append([t["category"], t["name"], t["tier"], t["desc"], t["licence"], t["containers"], t["home"], t["training"]])
    ws = wb.create_sheet("Featured courses")
    ws.append(["Domain", "Course", "Provider", "Level", "Cost", "Link"])
    for d, cs in ctx["featured"].items():
        for c in cs:
            ws.append([d, clean(c["course_name"]), clean(c["provider"]), clean(c["level"]), clean(c["cost_model"]),
                       clean(c["link"])])
    ws = wb.create_sheet("AU course candidates")
    ws.append(["Proposed", "Record", "Reason", "Course", "Provider", "Format", "Pace", "Enrolment status",
               "Next start", "Cost", "Link", "DReSA check", "Note"])
    for cand in sorted(candidates, key=lambda x: (x["proposed"], clean(x["course"]["provider"]))):
        c = cand["course"]
        ws.append([cand["proposed"], cand.get("record", ""), cand["reason"], clean(c["course_name"]),
                   clean(c["provider"]), clean(c["format"]), clean(c["learning_pace"]),
                   clean(c["enrolment_status"]), clean(c["next_start_date"]), clean(c["cost_model"]),
                   clean(c["link"]), cand["dresa"], cand["note"]])
    for sheet in wb:
        sheet.freeze_panes = "A2"
    wb.save(path)


if __name__ == "__main__":
    main()
