---
title: "Extraction Instructions"
author: "ARDC Learning Needs Project Team"
date: "June 2026"
---

# Extraction Instructions: LLM-Assisted Grey Literature Review — Online Training Courses for Health Researchers

## Purpose

This file tells Claude what to do during an extraction session. Read it fully before beginning any searching or extraction.

This project identifies online training courses relevant to Australian health researchers, as part of ARDC Work Package 6.2. The search covers 84 tools and methods across six domains: Analysis Methods, Conversational AI & Coding Co-pilots, Domain-Specific Tools, ML Frameworks & Methods, No Code / Low Code, and Programming & Environments.

**Claude's role is extraction only.** Find courses, record them fully and accurately, and deliver the output file. Do not apply selection criteria, make include/exclude judgements, or attempt to deduplicate across sessions. Duplicates are expected — the same course may appear across multiple sessions and is handled downstream by the researcher.

---

## Required Files

Four files must be uploaded at the start of every session. Confirm access to all four and confirm today's date before doing anything else.

| File | Purpose |
|---|---|
| `extraction_instructions.md` | This file. Read in full before starting. |
| `6_2_extraction_template.xlsx` | Output workbook. Deliver all extracted data using this template. |
| `tools_and_domains.csv` | The Research Tools and Methods framework — 84 tools across 6 domains. Read this fresh every session; never rely on a previously seen version. |
| `trusted_providers.xlsx` | List of trusted providers with catalogue URLs and search notes. |

---

## Session Structure

Follow these steps in order for every session.

1. **Load reference files** — read `tools_and_domains.csv` to load the current framework. Confirm all four files are accessible and state today's date.
2. **Confirm scope** — confirm the provider being searched (Phase 1) or the tool being searched (Phase 2) before beginning.
3. **Search** — navigate the provider's catalogue directly at the `catalogue_url` from `trusted_providers.xlsx` (Phase 1), or run multiple open web search queries (Phase 2). Fetch individual course pages to extract details — do not rely on catalogue listings alone.
4. **Extract** — record all courses found in both output sheets. Do not screen, filter, or suppress duplicates. For large catalogues, deliver the output file at natural checkpoints as well as at session end.
5. **Summarise** — at session end, provide:
   - Provider or tool searched, and date
   - Search strings used (Phase 2)
   - Total records extracted
   - Framework tools covered across extracted courses
   - Any tools or providers encountered that are not in the current framework — flag these; do not add them to `course_tools`
   - Any sources that could not be fetched (login walls, paywalls, dead links, JavaScript-rendered pages)
   - Suggested scope for the next session

---

## Output File

Deliver output as a populated `.xlsx` file using the extraction template. Do not print tables in the chat.

The workbook has two data sheets:

### Sheet 1: `coursework_resources`

One row per course found.

| Column | Type | Notes |
|---|---|---|
| course_id | Text (8-char hash) | MD5 hash of canonical course URL — see Generating course_id below |
| link | URL | Direct link to course page on the provider's own site — not a search result or aggregator listing. Record this even if the page itself could not be fetched directly; see "Handling Blocked or Inaccessible Course Pages" below. |
| select_reject | — | **Leave blank — researcher only** |
| select_justification | — | **Leave blank — researcher only** |
| course_name | Text | Full official name as listed on the course page |
| provider | Text | Organisation offering the course |
| country | Text | Country of the course provider. Use `USA` and `UK` consistently — not full country names — to match existing data conventions. |
| health_domain_relevance | Categorical | Whether the course content explicitly relates to the health/clinical/medical domain, regardless of whether it is framed as "research." Do not assess general applicability — only record what is directly stated on the course page. Values: `No`; `Yes - low` (health mentioned briefly or as one example among many); `Yes - medium` (health context is a recurring theme); `Yes - high` (health data, clinical datasets, or health research is a primary focus). Leave blank only if the course page cannot be accessed. Used as a dashboard filter for health-specific content. |
| health_domain_evidence | Text | Specific evidence from the course page supporting the `health_domain_relevance` rating — quote or paraphrase health dataset names, clinical examples, or health research framing. Populate only when `health_domain_relevance` is `Yes - low`, `Yes - medium`, or `Yes - high`. Do not infer. **Leave the cell genuinely blank if there is nothing to report — never write "nil," "Not stated," or similar placeholder text.** |
| notes | Text | Any additional observations — access issues, unusual format, whether the resource is a platform rather than a single course, etc. Health-specific evidence belongs in `health_domain_evidence`, not here. |
| level | Ordinal | Beginner, Intermediate, Advanced, Expert |
| delivery_platform | Categorical | Online, In-person, Blended. Use exact casing — do not write lowercase variants or combined values (e.g. "In-person / online"); if a course genuinely spans two modes, choose `Blended`. |
| format | Categorical | Workshop, Conference, Short course, MOOC, Degree, Webinar, Specialization, Professional Certificate. Use exact casing from this list — do not invent close variants. |
| learning_pace | Categorical | Self-paced, Instructor-paced, Cohort-based, Intensive bootcamp, Hybrid, Mentor-led. Use exact casing — do not write lowercase variants. |
| enrolment_status | Categorical | Answers "when can I start?" — distinct from `learning_pace`. Values: `Open enrolment` (can start anytime — applies to virtually all self-paced courses); `Scheduled cohort — open` (fixed start dates, registration currently open); `Scheduled cohort — closed` (fixed start dates, not currently open for registration); `One-time event — passed` (delivered live/once, not being repeated — common for workshops/webinars); `Not stated`. Used as a dashboard filter to exclude dead-end course listings. |
| next_start_date | Text | The next upcoming cohort start date, as stated on the course page. Record exactly as stated — a specific date (e.g. "March 2027"), a recurring pattern (e.g. "Rolling enrolment", "Every Monday"), or similar. Populate only when `enrolment_status` is `Scheduled cohort — open`. **If the date cannot be extracted — not stated, ambiguous, or the page gives no schedule information — leave the cell genuinely blank. Do not guess or infer a date.** |
| weekly_time_commitment | Ordinal | < 1hr, 1-3 hrs, 3-5 hrs, 5-10 hrs, 10+ hrs. **Map any weekly time stated on the course page into the nearest bucket — never record the raw stated text (e.g. "3 hours per week") directly in this field.** |
| duration | Text | Free text — e.g. "6 weeks", "3 hours" — as stated on the course page. **If duration is not stated, leave the cell genuinely blank — never write "Not stated," "Not specified," "N/A," or similar placeholder text.** |
| primary_language | Text/Multiple | Programming language(s) used. Comma-separated if multiple. Use `No programming` for tool-only courses with no coding; `Methods` for theory-only courses with no software component. Leave blank if not stated. |
| primary_tools | Text/Multiple | Comma-separated list of all tools taught. Use consistent formatting: comma-and-space between items (e.g. "Python, scikit-learn, PyTorch"), no trailing punctuation, standard capitalisation for known tool names. |
| key_topics | Text | Comma-separated list of main topics covered |
| target_audience | Text | Intended learners — as described on the course page |
| cost_model | Categorical | The primary cost model as advertised on the course page. Use these decision rules: `Free` (entire course, all content and any certificate, costs nothing, no account/subscription required); `Free to audit` (content is free to view/complete, but a fee applies for graded work, certificate, or credential); `Freemium` (some content/modules free, but full course or advanced modules require payment); `Paid` (one-time fee required to access any course content); `Subscription` (access requires an ongoing platform subscription, e.g. Coursera Plus, LinkedIn Learning, rather than a per-course fee); `Institutional access` (access is gated behind an institutional licence/account — university, hospital, etc. — not available to the general public directly). |
| price_lowest_USD | Numerical | The cheapest way to access course content, in USD — often $0 for audit-only access. Convert to USD using the exchange rate on the date of extraction. Use `not_available` if no price is stated anywhere on the course page — do not infer from similar courses on the same platform. |
| price_certificate_USD | Numerical | The cost of the credentialed/certificate track, in USD, if different from `price_lowest_USD`. Leave blank if there is no separate certificate/credential price (e.g. course is free throughout, or is `Paid` with one price covering everything). Convert to USD using the exchange rate on the date of extraction. Use `not_available` if a certificate exists but no price is stated. |
| access_notes | Text | One-line free-text capture of the actual pricing structure as stated on the course page — e.g. "Free to audit; $49 USD for certificate (Coursera, checked 2026-06-24)." Always include the exchange-rate date used for any currency conversion, so the figure is auditable later. Check the course's own pricing/enrolment page first, not the catalogue search result, before recording prices. |
| research_workflow_relevance | Categorical | Whether the course is designed for people conducting research — research methods, workflows, or academic skill-building — regardless of subject domain. Distinct from `health_domain_relevance`: a course can be highly research-orientated without any health content, or health-relevant without being research-methods focused. Values: `Yes - High`, `Yes - Moderate`, `Yes - Low`, `No`. Use exact casing — do not write lowercase variants. Used as a dashboard filter for research-workflow content. |
| qualification | Categorical | Certificate, Microcredential, Specialisation, No credential, CPD points. **Map the provider's own credential label into one of these five categories — do not record the provider's own wording.** E.g. "Nanodegree" → `Certificate`; "Course Certificate (Coursera)" → `Certificate`; "Completion certificate" → `Certificate`; "Certificate (accredited)" → `Certificate`; "None" → `No credential`. |
| course_of_interest | — | **Leave blank — researcher only** |
| prerequisites | Text | Free text — e.g. "Basic Python". **Distinguish "not stated" from "explicitly none":** if the course page explicitly states there are no prerequisites, record `None`. If the page simply doesn't mention prerequisites at all, leave the cell genuinely blank — do not write `None stated`, `N/A`, or similar placeholder text. |
| audited | categorical | **Leave blank — researcher only** |
**The following five fields (`framework_coverage`, `model_types_covered`, `hands_on_coding`, `API_integration`, `ethics_AI_safety`) each have their own distinct controlled vocabulary — do not borrow values from a neighbouring field in this list. If the course has no AI/LLM content at all, leave all five fields genuinely blank — do not write `N/A`, `Not covered`, or `No` as a substitute for blank.**

| framework_coverage | Text/Multiple | AI/ML frameworks taught — e.g. LangChain, PyTorch, Hugging Face. Free text; does not use the Yes/No or Covered/Not covered scales from the other four fields in this group. Leave blank if not applicable. |
| model_types_covered | Text/Multiple | Types of AI/LLM models covered — e.g. GPT, BERT, RAG systems. Free text; does not use the Yes/No or Covered/Not covered scales from the other four fields in this group. Leave blank if not applicable. |
| hands_on_coding | Categorical | `Yes - Extensive`, `Yes - Moderate`, `Yes - Light`, `No - Conceptual`. Use exact casing and exact values from this list only — do not write bare `Yes`/`No`, `unknown`, or `Limited`. |
| API_integration | Categorical | `Yes`, `No`, `Limited`. Use exact values from this list only — do not write `Covered`/`Not covered` (those belong to `ethics_AI_safety`). Leave blank if not an AI/LLM course. |
| ethics_AI_safety | Categorical | `Covered`, `Limited`, `Not covered`, `N/A`. Use exact values from this list only — do not write `Yes`/`No`/`Yes - Moderate` (those belong to `hands_on_coding`/`API_integration`). |
| no_longer_maintained | Categorical | `Yes`, or leave blank. Set to Yes only if the course page explicitly states it is no longer maintained or updated. |

---

### Handling Blocked or Inaccessible Course Pages

The provider's own course page is always the first choice and the preferred source. If it cannot be fetched directly — blocked by robots.txt, behind a login wall, rendered entirely in JavaScript with no extractable HTML, or returning an error — work through the following fallback sources, roughly in order of reliability, before leaving a course out of the database entirely:

1. **Cached or archived versions of the page** — e.g. a search engine cache, the Wayback Machine, or a cached snippet shown directly in search results.
2. **The provider's own secondary materials** — official brochures or PDFs, press releases, marketing landing pages, official social media posts, or video descriptions (e.g. an official YouTube upload describing the course).
3. **Aggregator or third-party listings** — Class Central, Coursera/edX search result pages, course review sites, or similar — used as a content source, not as the recorded `link`.
4. **Search result snippets and SEO meta descriptions** — the short description text shown in search results, when no fuller source is accessible.

**Rules that apply regardless of which fallback is used:**

- **Record the canonical provider URL in `link` even if its content could not be fetched directly** — do not substitute an aggregator URL unless no individual course page URL exists at all (in which case, record the closest available URL — e.g. a category or catalogue page — and say so in `notes`).
- **Always note the fallback source and the access issue in `notes`** — e.g. *"Course page blocked by robots.txt; course name and description sourced from Class Central listing and search snippet text."* This is not optional — every record built from a fallback source must be flagged so it can be distinguished from a directly-fetched record.
- **Only populate stable, low-risk fields from fallback sources**: `course_name`, `provider`, `country`, `level`, `key_topics`, `target_audience`, `primary_language`, `primary_tools`, `format`, `delivery_platform`, `learning_pace`, `qualification`.
- **Never populate volatile or evidence-dependent fields from a fallback source — leave them blank instead**: `price_lowest_USD`, `price_certificate_USD`, `access_notes`, `enrolment_status`, `next_start_date`, `health_domain_evidence`. These fields depend on exact, current wording from the course page itself; a stale cached snippet or a third-party aggregator's summary is not a reliable source for them, and a wrong value is worse than a blank one.
- **`health_domain_relevance` may still be assessed from a fallback source** (since it's a judgement based on the available description) **but `health_domain_evidence` must stay blank** unless the actual course page text is available to quote or paraphrase from.

---

### Sheet 2: `course_tools`

One row per tool per course. A course covering R, Python, and Regression generates three rows, all sharing the same `course_id`.

**Identify the tool first, then look up its domain** — the domain is derived from the tool using the framework; do not select it independently.

| Column | Notes |
|---|---|
| course_id | Must match the course_id in coursework_resources |
| learning_need_tool | Map to the closest matching tool name in `tools_and_domains.csv`. Use framework names only — do not invent new entries. If a course teaches something that does not reasonably match any framework tool, record it in `primary_tools` in coursework_resources and flag it in the session summary. |
| learning_needs_domain | Derived by looking up which domain the tool belongs to in `tools_and_domains.csv`. Do not select independently. |

---

## Worked Example: Cost and Access Fields

Coursera course, audit free, certificate $49 USD as of extraction date:

- `cost_model` = `Free to audit`
- `price_lowest_USD` = `0`
- `price_certificate_USD` = `49`
- `access_notes` = `"Free to audit; $49 USD for certificate (Coursera, checked 2026-06-24)."`

---

## Generating course_id

The `course_id` is an 8-character MD5 hash of the canonical course URL. It is deterministic — the same URL always produces the same ID.

```r
library(digest)
course_id <- substr(digest(url, algo = "md5"), 1, 8)
```

- Always hash the canonical course URL — the direct link to the course page, not a search result or redirect
- Strip trailing slashes before hashing
- Do not use aggregator listing URLs (e.g. ClassCentral, Coursera search pages) — use the provider's own course page

---

## Extraction Quality Rules

- **Record everything found** — do not exclude based on perceived relevance; that is the researcher's job at screening
- **Only record what is stated on the course page** — do not infer, estimate, or guess field values
- **Leave a field blank if the information is not available** — a blank is always preferable to a guess
- **`select_reject`, `select_justification`, `course_of_interest`, and `ARDC_audited` must always be left blank** — these are screening-stage fields populated by the researcher only
- **Duplicates across sessions are expected** — extract fully every time; do not attempt to detect or suppress them
- **Use the provider's own course page** where possible, not an aggregator listing
- **Always record the direct course URL**, not a search result page or category listing
- **Tool names in `course_tools` must match the framework** — use `tools_and_domains.csv` names only; flag anything that doesn't match in the session summary
- **Use the `notes` field** to flag anything unusual — access issues, ambiguous content, platform vs single course
- **Use `health_domain_evidence`** to record specific supporting evidence when `health_domain_relevance` is `Yes - low`, `Yes - medium`, or `Yes - high` — quote or paraphrase from the course page; never infer; leave genuinely blank if there is nothing to report
- **`research_workflow_relevance` and `health_domain_relevance` are independent filters** — assess each on its own terms; a course can score highly on one without the other
- **`enrolment_status` is distinct from `learning_pace`** — pace describes how the course is delivered, enrolment_status describes whether/when a person can currently join
- **`next_start_date` is high-volatility data** — it goes stale the moment the cohort starts or the schedule changes; treat it as a snapshot at extraction time, not a durable fact. Leave blank rather than guess if the page doesn't clearly state it.
- **`framework_coverage`, `model_types_covered`, `hands_on_coding`, `API_integration`, and `ethics_AI_safety` each have their own controlled vocabulary** — do not borrow values from a neighbouring field in this group; if a course has no AI/LLM content, leave all five blank rather than writing `N/A`/`Not covered`/`No`
- **`qualification` must be mapped into the five controlled categories** — never record the provider's own credential wording verbatim
- **`prerequisites` distinguishes "explicitly none" (`None`) from "not stated" (blank)** — do not write `None stated` or similar
- **`primary_tools` uses consistent comma-and-space formatting** with standard tool-name capitalisation
- **`country` uses `USA` and `UK`**, not full country names, for consistency with existing data
- **If a course page is blocked or inaccessible**, follow the fallback order in "Handling Blocked or Inaccessible Course Pages" — always flag the fallback source in `notes`, and never populate volatile fields (`price_lowest_USD`, `price_certificate_USD`, `access_notes`, `enrolment_status`, `next_start_date`, `health_domain_evidence`) from a fallback source
- **Use `no_longer_maintained`** only when the course page explicitly states the course is no longer maintained
- **Check the course's own pricing/enrolment page first** for `cost_model`, `price_lowest_USD`, and `price_certificate_USD` — pricing is often on a separate page from the course description, not the catalogue listing
- **Capture tiered pricing explicitly** — if a course has both a free/audit option and a paid certificate, record both in `price_lowest_USD` and `price_certificate_USD` rather than collapsing to a single value
- **Always state the exchange-rate date** in `access_notes` when a currency conversion was used, so the figure is auditable later
